import logging
import threading
from fastapi import FastAPI
from src.kafka_consumer import consume_order_created_events
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Inventory Service")

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    # Start Kafka consumer in background
    consumer_thread = threading.Thread(target=consume_order_created_events, daemon=True)
    consumer_thread.start()
    
    # Run API for health checks
    uvicorn.run(app, host="0.0.0.0", port=8001)
