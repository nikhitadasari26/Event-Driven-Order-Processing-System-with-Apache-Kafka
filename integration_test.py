import requests
import time
import sys

BASE_URL = "http://localhost:8080/api/orders"

def test_success_flow():
    print("Testing End-to-End Success Flow...")
    payload = {
        "user_id": "integration_tester_1",
        "items": [
            {"sku": "sku-001", "quantity": 1}
        ]
    }
    r = requests.post(BASE_URL, json=payload)
    if r.status_code != 202:
        raise AssertionError(f"Failed to create order: {r.text}")
    
    order_id = r.json()["order_id"]
    print(f"  [+] Order created (ID: {order_id}). Waiting for async processing via Kafka...")
    
    # Wait for async outbox, kafka transmission, and inventory processing
    time.sleep(5)
    
    r_get = requests.get(f"{BASE_URL}/{order_id}")
    if r_get.status_code != 200:
        raise AssertionError(f"Failed to retrieve order: {r_get.text}")
        
    status = r_get.json()["status"]
    print(f"  [+] Final Status recorded in DB: {status}")
    if status != "PROCESSING":
        raise AssertionError(f"Expected PROCESSING status, but got {status}")

def test_failure_flow_insufficient_stock():
    print("\nTesting End-to-End Failure Flow (Insufficient Stock)...")
    payload = {
        "user_id": "integration_tester_2",
        "items": [
            {"sku": "sku-001", "quantity": 99999} # Impossible quantity
        ]
    }
    r = requests.post(BASE_URL, json=payload)
    if r.status_code != 202:
        raise AssertionError(f"Failed to create order: {r.text}")
        
    order_id = r.json()["order_id"]
    print(f"  [+] Order created (ID: {order_id}). Waiting for async processing via Kafka...")
    
    time.sleep(5)
    
    r_get = requests.get(f"{BASE_URL}/{order_id}")
    if r_get.status_code != 200:
        raise AssertionError(f"Failed to retrieve order: {r_get.text}")
        
    status = r_get.json()["status"]
    print(f"  [+] Final Status recorded in DB: {status}")
    if status != "FAILED":
        raise AssertionError(f"Expected FAILED status, but got {status}")

if __name__ == "__main__":
    try:
        test_success_flow()
        test_failure_flow_insufficient_stock()
        print("\n===== ALL E2E INTEGRATION TESTS PASSED SUCCESSFULLY =====")
    except AssertionError as e:
        print(f"\n[!] INTEGRATION TEST FAILED: {e}")
        sys.exit(1)
    except Exception as ex:
        print(f"\n[!] UNEXPECTED ERROR: {ex}")
        sys.exit(1)
