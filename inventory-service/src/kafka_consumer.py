import os
import json
import logging
import time
from confluent_kafka import Consumer, Producer, KafkaException
from tenacity import retry, wait_exponential, stop_after_attempt
from src.inventory_logic import deduct_inventory_idempotently

logger = logging.getLogger(__name__)

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_ORDERS = "orders.created"
KAFKA_TOPIC_DLQ = "inventory.orders.dlq"
KAFKA_GROUP_ID = "inventory-service-group"

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
    'client.id': 'inventory-service-dlq'
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
        logger.error(f"Sent message to DLQ: {message_key}")
    except Exception as e:
        logger.error(f"Failed to send message to DLQ: {str(e)}")

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
def process_message_with_retry(msg_key, msg_value):
    # Parse event
    data = json.loads(msg_value)
    order_id = data.get("order_id")
    items = data.get("items")
    event_id = data.get("event_id")
    
    if not order_id or not items or not event_id:
        logger.error(f"Invalid message format for order {order_id}")
        return
    
    # Deduct inventory (this also handles idempotency internally)
    deduct_inventory_idempotently(order_id, items, event_id)

def consume_order_created_events():
    consumer = Consumer(consumer_conf)
    consumer.subscribe([KAFKA_TOPIC_ORDERS])
    
    logger.info(f"Subscribed to {KAFKA_TOPIC_ORDERS} in group {KAFKA_GROUP_ID}")
    
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                continue
            
            msg_key = msg.key().decode('utf-8') if msg.key() else None
            msg_value = msg.value().decode('utf-8')
            
            try:
                process_message_with_retry(msg_key, msg_value)
                # Commit offset manually after successful processing
                consumer.commit(asynchronous=False)
            except Exception as e:
                logger.error(f"Processing failed after retries for message {msg_key}: {str(e)}")
                send_to_dlq(msg_key, msg_value, str(e))
                # Skip and commit offset to move to next message
                consumer.commit(asynchronous=False)
                
    except KeyboardInterrupt:
        logger.info("Stopping consumer...")
    finally:
        consumer.close()
