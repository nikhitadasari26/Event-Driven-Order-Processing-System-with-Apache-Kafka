import logging
import json
import os
import uuid
from sqlalchemy.orm import Session
from src.database import Inventory, ProcessedEvent, OrderStatusUpdate, InventorySession, OrderSession
from confluent_kafka import Producer

logger = logging.getLogger(__name__)

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_INVENTORY_UPDATED = "inventory.updated"
KAFKA_TOPIC_ORDER_FAILED = "order.failed"

producer_conf = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'client.id': 'inventory-service-producer'
}
producer = Producer(producer_conf)

def publish_event(topic, key, payload):
    try:
        producer.produce(topic, key=key, value=json.dumps(payload))
        producer.flush()
        logger.info(f"Published event to {topic}")
    except Exception as e:
        logger.error(f"Failed to publish event to {topic}: {str(e)}")

def deduct_inventory_idempotently(order_id: str, items: list, event_id: str) -> bool:
    inventory_db = InventorySession()
    order_db = OrderSession()
    
    try:
        # 1. Idempotency Check
        existing_event = inventory_db.query(ProcessedEvent).filter(
            ProcessedEvent.consumer_id == "inventory-service",
            ProcessedEvent.event_id == event_id
        ).first()
        
        if existing_event:
            logger.info(f"Event {event_id} already processed for order {order_id}. Skipping.")
            return True
        
        # 2. Check and Deduct Stock
        success = True
        missing_sku = None
        
        # Start transaction on inventory_db
        for item in items:
            sku = item.get("sku")
            qty = item.get("quantity")
            
            product = inventory_db.query(Inventory).filter(Inventory.sku == sku).first()
            if not product or product.stock < qty:
                success = False
                missing_sku = sku
                break
        
        if success:
            # Deduct stock
            for item in items:
                sku = item.get("sku")
                qty = item.get("quantity")
                product = inventory_db.query(Inventory).filter(Inventory.sku == sku).first()
                product.stock -= qty
            
            # Record processed event
            processed_event = ProcessedEvent(
                consumer_id="inventory-service",
                event_id=event_id
            )
            inventory_db.add(processed_event)
            inventory_db.commit()
            
            # 3. Update Order Status to PROCESSING
            order = order_db.query(OrderStatusUpdate).filter(OrderStatusUpdate.id == order_id).first()
            if order:
                order.status = 'PROCESSING'
                order_db.commit()
            
            # 4. Success Event
            inventory_event_id = str(uuid.uuid4())
            publish_event(KAFKA_TOPIC_INVENTORY_UPDATED, order_id, {
                "order_id": order_id,
                "status": "PROCESSING",
                "event_id": inventory_event_id,
                "source_event_id": event_id
            })
            return True
        else:
            # Insufficient stock
            logger.warning(f"Insufficient stock for SKU {missing_sku} in order {order_id}")
            
            # Record processed event anyway to avoid infinite retries of unprocessable order
            processed_event = ProcessedEvent(
                consumer_id="inventory-service",
                event_id=event_id
            )
            inventory_db.add(processed_event)
            inventory_db.commit()
            
            # Update Order Status to FAILED
            order = order_db.query(OrderStatusUpdate).filter(OrderStatusUpdate.id == order_id).first()
            if order:
                order.status = 'FAILED'
                order_db.commit()
            
            # Failure Event
            failure_event_id = str(uuid.uuid4())
            publish_event(KAFKA_TOPIC_ORDER_FAILED, order_id, {
                "order_id": order_id,
                "status": "FAILED",
                "reason": f"Insufficient stock for SKU {missing_sku}",
                "event_id": failure_event_id,
                "source_event_id": event_id
            })
            return False

    except Exception as e:
        inventory_db.rollback()
        order_db.rollback()
        logger.error(f"Error processing inventory for order {order_id}: {str(e)}")
        raise e # Re-raise for retry mechanism
    finally:
        inventory_db.close()
        order_db.close()
