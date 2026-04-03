# Event-Driven Order Processing System with Apache Kafka

A resilient and scalable order processing system built with Event-Driven Architecture (EDA) principles.

## Architecture

- **Order Service**: REST API that accepts orders and stores them in MySQL. Uses the **Transactional Outbox** pattern to ensure atomicity between database updates and Kafka events.
- **Inventory Service**: Consumes `OrderCreated` events and deducts stock from its own database. It processes messages **idempotently** and notifies the Order Service of the result via database updates and Kafka events (`InventoryUpdated`, `OrderFailed`).
- **Notification Service**: Consumes events from all services and logs notifications to the console. It also implements **idempotency** to avoid duplicate notifications.
- **Apache Kafka**: The central message broker for asynchronous communication.
- **MySQL**: Persistent storage for orders and inventory.

## Project Structure

```
├── docker-compose.yml
├── .env.example
├── order-service/        # Order management & Event Producer
├── inventory-service/    # Stock management & Consumer
├── notification-service/ # Notification simulator & Consumer
├── sql/                  # MySQL initialization & Seeding
└── README.md
```

## Setup and Running

### Prerequisites
- Docker and Docker Compose

### Start the System

1.  Clone the repository and navigate to the project root.
2.  Run the following command:
    ```bash
    docker-compose up --build
    ```
3.  Wait for all services to be healthy (Kafka and MySQL may take a few seconds).

### Verify Services

- **Order Service**: [http://localhost:8080/health](http://localhost:8080/health)
- **Inventory Service**: [http://localhost:8001/health](http://localhost:8001/health)
- **Notification Service**: [http://localhost:8002/health](http://localhost:8002/health)

## Usage

### 1. Create an Order
Use `curl` to send a POST request to the Order Service:
```bash
curl -X POST http://localhost:8080/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "items": [
      {"sku": "sku-001", "quantity": 1},
      {"sku": "sku-002", "quantity": 2}
    ]
  }'
```

### 2. View Order Status
Retrieve the order details using the `order_id` from the response above:
```bash
curl http://localhost:8080/api/orders/{orderId}
```

## Testing

### Unit Tests
Comprehensive unit tests with database mocking are provided for all microservices. 

To run them, execute the following commands while the containers are running:

```bash
# Order Service Tests
docker-compose exec order-service pytest tests/ -v

# Inventory Service Tests
docker-compose exec inventory-service pytest tests/ -v

# Notification Service Tests
docker-compose exec notification-service pytest tests/ -v
```

### End-to-End Integration Testing
An automated integration test script `integration_test.py` is provided at the root of the project. It tests both the successful order flow and the insufficient stock failure flow by making live REST API calls and asserting final database states.

To run the integration tests (requires `requests` library locally):
```bash
pip install requests
python integration_test.py
```

## Resilience Features
- **Transactional Outbox**: Events are saved in the same transaction as the order. A background poller ensures they reach Kafka even if the API crashes.
- **Idempotency**: Consumers track processed `event_id`s in a `processed_events` table (handled entirely via logic without requiring distributed locks in this scope).
- **DLQ**: Unprocessable messages are published to `{service}.dlq` topics.
- **Retry**: Consumer implementation utilizes `tenacity` for exponential backoff retries on transient errors.
