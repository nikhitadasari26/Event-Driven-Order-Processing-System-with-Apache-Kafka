import os
import uuid
import json
import logging
import threading
import time
from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from src.database import get_db, Order, OutboxEvent, SessionLocal
from confluent_kafka import Producer

# Configure logging
from pythonjsonlogger import jsonlogger
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
logHandler.setFormatter(formatter)
logging.root.addHandler(logHandler)
logging.root.setLevel(logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI(title="Order Service")

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_ORDERS = "orders.created"

producer_conf = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'client.id': 'order-service-producer'
}
producer = Producer(producer_conf)

def delivery_report(err, msg):
    if err is not None:
        logger.error(f"Message delivery failed: {err}")
    else:
        logger.info(f"Message delivered to {msg.topic()} [{msg.partition()}]")

class OrderItem(BaseModel):
    sku: str
    quantity: int

class OrderCreate(BaseModel):
    user_id: str
    items: List[OrderItem]

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/orders", status_code=status.HTTP_202_ACCEPTED)
async def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    # Validate items
    if not order_data.items:
        raise HTTPException(status_code=400, detail="Items list cannot be empty")
    
    for item in order_data.items:
        if item.quantity <= 0:
            raise HTTPException(status_code=400, detail=f"Invalid quantity for SKU {item.sku}: must be > 0")
    
    order_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    
    # Create Order object
    new_order = Order(
        id=order_id,
        user_id=order_data.user_id,
        items=[item.model_dump() for item in order_data.items],
        status='PENDING',
        event_id=event_id
    )
    
    # Create OutboxEvent object
    outbox_event = OutboxEvent(
        id=event_id,
        aggregate_type="Order",
        aggregate_id=order_id,
        event_type="OrderCreated",
        payload={
            "order_id": order_id,
            "user_id": order_data.user_id,
            "items": [item.model_dump() for item in order_data.items],
            "event_id": event_id
        }
    )
    
    try:
        db.add(new_order)
        db.add(outbox_event)
        db.commit()
        logger.info(f"Order {order_id} created and outbox event {event_id} stored.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create order: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return {"order_id": order_id, "status": "PENDING"}

@app.get("/api/orders/{order_id}")
async def get_order(order_id: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "order_id": order.id,
        "status": order.status,
        "items": order.items,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat()
    }

# Transactional Outbox Poller
def outbox_poller():
    logger.info("Starting Outbox Poller thread...")
    while True:
        db = SessionLocal()
        try:
            # Fetch unprocessed events
            events = db.query(OutboxEvent).filter(OutboxEvent.processed == False).all()
            for event in events:
                # Publish to Kafka
                try:
                    payload = json.dumps(event.payload)
                    producer.produce(
                        KAFKA_TOPIC_ORDERS, 
                        key=event.aggregate_id, 
                        value=payload, 
                        callback=delivery_report
                    )
                    producer.flush()
                    
                    # Mark as processed
                    event.processed = True
                    db.commit()
                    logger.info(f"Published event {event.id} for order {event.aggregate_id}")
                except Exception as ex:
                    logger.error(f"Failed to publish event {event.id}: {str(ex)}")
        except Exception as e:
            logger.error(f"Outbox Poller error: {str(e)}")
        finally:
            db.close()
        time.sleep(1) # Poll every second

@app.on_event("startup")
def startup_event():
    logger.info("FastAPI starting up. Initializing Outbox Poller...")
    poller_thread = threading.Thread(target=outbox_poller, daemon=True)
    poller_thread.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

