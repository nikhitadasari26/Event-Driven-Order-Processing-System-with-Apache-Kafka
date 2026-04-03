import pytest
from unittest.mock import patch, MagicMock
from src.kafka_consumer import is_processed, simulate_notification
import logging

@patch('src.kafka_consumer.SessionLocal')
def test_is_processed(mock_session_local):
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    # Simulate existing event
    mock_db.query().filter().first.return_value = True
    assert is_processed("evt_1") is True
    
    # Simulate new event
    mock_db.query().filter().first.return_value = None
    assert is_processed("evt_2") is False

def test_simulate_notification_logging(caplog):
    # Set caplog to capture INFO level logs
    with caplog.at_level(logging.INFO):
        simulate_notification("orders.created", {"order_id": "o1", "event_id": "e1"})
        simulate_notification("inventory.updated", {"order_id": "o1", "event_id": "e2"})
        
    with caplog.at_level(logging.WARNING):
        simulate_notification("order.failed", {"order_id": "o2", "event_id": "e3", "reason": "Out of stock"})
        
    assert "Order Received" in caplog.text
    assert "OrderID: o1" in caplog.text
    assert "Inventory Deducted" in caplog.text
    assert "Order FAILED alert" in caplog.text
    assert "Out of stock" in caplog.text
