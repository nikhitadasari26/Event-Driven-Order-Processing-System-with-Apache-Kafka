import os
import json
import logging
import time
from confluent_kafka import Consumer, Producer
from src.database import ProcessedEvent, SessionLocal

logger = logging.getLogger(__name__)

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPICS = ["orders.created", "inventory.updated", "order.failed"]
KAFKA_GROUP_ID = "notification-service-group"
KAFKA_TOPIC_DLQ = "notification.dlq"

# Consumer Configuration
consumer_conf = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'group.id': KAFKA_GROUP_ID,
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False
}

# DLQ Producer Configuration
dlq_producer_conf = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'client.id': 'notification-service-dlq'
}
dlq_producer = Producer(dlq_producer_conf)

def send_to_dlq(message_key, message_value, error_msg):
    try:
        payload = {
            "original_message": json.loads(message_value) if isinstance(message_value, (str, bytes)) else message_value,
            "error": error_msg,
            "timestamp": time.time()
        }
        dlq_producer.produce(KAFKA_TOPIC_DLQ, key=message_key, value=json.dumps(payload))
        dlq_producer.flush()
        logger.error(f"Notification Sent to DLQ: {message_key}")
    except Exception as e:
        logger.error(f"Failed to send notification to DLQ: {str(e)}")

def is_processed(event_id: str) -> bool:
    db = SessionLocal()
    try:
        event = db.query(ProcessedEvent).filter(
            ProcessedEvent.consumer_id == "notification-service",
            ProcessedEvent.event_id == event_id
        ).first()
        return event is not None
    finally:
        db.close()

def mark_as_processed(event_id: str):
    db = SessionLocal()
    try:
        processed_event = ProcessedEvent(
            consumer_id="notification-service",
            event_id=event_id
        )
        db.add(processed_event)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to mark event {event_id} as processed: {str(e)}")
    finally:
        db.close()

def simulate_notification(topic, data):
    order_id = data.get("order_id")
    event_id = data.get("event_id")
    
    if topic == "orders.created":
        logger.info(f" >>> [NOTIFICATION SERVICE] Order Received. Sending Confirmation Email | OrderID: {order_id} | EventID: {event_id}")
    elif topic == "inventory.updated":
        logger.info(f" >>> [NOTIFICATION SERVICE] Inventory Deducted. Notifying Processing Start | OrderID: {order_id} | EventID: {event_id}")
    elif topic == "order.failed":
        reason = data.get("reason", "unknown")
        logger.warning(f" >>> [NOTIFICATION SERVICE] Order FAILED alert. Reason: {reason} | OrderID: {order_id} | EventID: {event_id}")

def consume_notification_events():
    consumer = Consumer(consumer_conf)
    consumer.subscribe(TOPICS)
    
    logger.info(f"Subscribed to {TOPICS} in group {KAFKA_GROUP_ID}")
    
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                continue
            
            topic = msg.topic()
            msg_key = msg.key().decode('utf-8') if msg.key() else None
            msg_value = msg.value().decode('utf-8')
            
            try:
                data = json.loads(msg_value)
                event_id = data.get("event_id")
                
                if not event_id:
                    logger.warning(f"Message missing event_id: {msg_value}")
                    consumer.commit(asynchronous=False)
                    continue
                
                # Idempotency Check
                if is_processed(event_id):
                    logger.info(f"Notification for event {event_id} already sent. Skipping.")
                else:
                    simulate_notification(topic, data)
                    mark_as_processed(event_id)
                
                consumer.commit(asynchronous=False)
                
            except Exception as e:
                logger.error(f"Failed to process notification for message {msg_key}: {str(e)}")
                send_to_dlq(msg_key, msg_value, str(e))
                consumer.commit(asynchronous=False)
                
    except KeyboardInterrupt:
        logger.info("Stopping consumer...")
    finally:
        consumer.close()
