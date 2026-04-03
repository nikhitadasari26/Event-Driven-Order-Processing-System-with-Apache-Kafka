import pytest
from unittest.mock import patch, MagicMock
from src.inventory_logic import deduct_inventory_idempotently

class MockProduct:
    def __init__(self, stock):
        self.stock = stock

class MockOrder:
    def __init__(self, status):
        self.status = status

@patch('src.inventory_logic.publish_event')
@patch('src.inventory_logic.InventorySession')
@patch('src.inventory_logic.OrderSession')
def test_deduct_inventory_success(mock_order_session, mock_inv_session, mock_publish):
    mock_inv_db = MagicMock()
    mock_order_db = MagicMock()
    mock_inv_session.return_value = mock_inv_db
    mock_order_session.return_value = mock_order_db
    
    # Simulate: No processed event, Item exists with enough stock, then deduct it
    mock_inv_db.query().filter().first.side_effect = [
        None,             # ProcessedEvent check
        MockProduct(10),  # Check stock
        MockProduct(10)   # Deduct stock loop
    ]
    
    mock_order = MockOrder('PENDING')
    mock_order_db.query().filter().first.return_value = mock_order
    
    items = [{"sku": "sku-1", "quantity": 1}]
    result = deduct_inventory_idempotently("ord_1", items, "evt_1")
    
    assert result is True
    assert mock_order.status == 'PROCESSING'
    mock_inv_db.commit.assert_called()
    mock_order_db.commit.assert_called()
    assert mock_publish.called

@patch('src.inventory_logic.publish_event')
@patch('src.inventory_logic.InventorySession')
@patch('src.inventory_logic.OrderSession')
def test_deduct_inventory_failure_no_stock(mock_order_session, mock_inv_session, mock_publish):
    mock_inv_db = MagicMock()
    mock_order_db = MagicMock()
    mock_inv_session.return_value = mock_inv_db
    mock_order_session.return_value = mock_order_db
    
    # Simulate: No processed event, Item has insufficient stock (0)
    mock_inv_db.query().filter().first.side_effect = [
        None,            # ProcessedEvent check
        MockProduct(0)   # Check stock -> goes to failure path
    ]
    
    mock_order = MockOrder('PENDING')
    mock_order_db.query().filter().first.return_value = mock_order
    
    items = [{"sku": "sku-1", "quantity": 10}]
    result = deduct_inventory_idempotently("ord_2", items, "evt_2")
    
    assert result is False
    assert mock_order.status == 'FAILED'
    # It still records the processed event to prevent endless retries
    mock_inv_db.commit.assert_called()
    assert mock_publish.called

@patch('src.inventory_logic.publish_event')
@patch('src.inventory_logic.InventorySession')
def test_deduct_inventory_idempotent_skip(mock_inv_session, mock_publish):
    mock_inv_db = MagicMock()
    mock_inv_session.return_value = mock_inv_db
    
    # Simulate: Event already processed exists
    mock_inv_db.query().filter().first.return_value = True 
    
    result = deduct_inventory_idempotently("ord_1", [], "evt_1")
    
    # Returns True implicitly and skips logic
    assert result is True
    assert mock_publish.called is False
