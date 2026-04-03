import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.database import get_db

client = TestClient(app)

# Dummy DB Session for Mocking
class MockSession:
    def add(self, *args, **kwargs):
        pass
    def commit(self):
        pass
    def rollback(self):
        pass
    def query(self, *args, **kwargs):
        return self
    def filter(self, *args, **kwargs):
        return self
    def first(self):
        from src.database import Order
        import datetime
        return Order(
            id="test-id", 
            user_id="u1", 
            items=[{"sku": "s1", "quantity": 1}],
            status="PENDING",
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
            event_id="evt-1"
        )

def override_get_db():
    yield MockSession()

app.dependency_overrides[get_db] = override_get_db

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_create_order_success():
    response = client.post("/api/orders", json={"user_id": "u1", "items": [{"sku": "sku-001", "quantity": 1}]})
    assert response.status_code == 202
    assert "order_id" in response.json()
    assert response.json()["status"] == "PENDING"

def test_create_order_validation_error_empty():
    response = client.post("/api/orders", json={"user_id": "u1", "items": []})
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]

def test_create_order_validation_error_qty():
    response = client.post("/api/orders", json={"user_id": "u1", "items": [{"sku": "s1", "quantity": 0}]})
    assert response.status_code == 400
    assert "Invalid quantity" in response.json()["detail"]

def test_get_order():
    response = client.get("/api/orders/test-id")
    assert response.status_code == 200
    assert response.json()["order_id"] == "test-id"
    assert response.json()["status"] == "PENDING"
