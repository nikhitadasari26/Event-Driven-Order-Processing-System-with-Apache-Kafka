# Order Service API Documentation

The Order Service provides endpoints for managing and tracking customer orders.

## Base URL
`http://localhost:8080/api`

## Endpoints

### 1. Create Order
**POST `/orders`**

Create a new order.

#### Request Body
```json
{
  "user_id": "string (UUID)",
  "items": [
    {
      "sku": "string",
      "quantity": "integer"
    }
  ]
}
```

#### Response (Success - 202 Accepted)
```json
{
  "order_id": "string (UUID)",
  "status": "PENDING"
}
```

#### Response (Validation Failure - 400 Bad Request)
```json
{
  "detail": "Items list cannot be empty"
}
```

---

### 2. Get Order Details
**GET `/orders/{orderId}`**

Retrieve details and status of an existing order.

#### Path Parameters
- `orderId`: The unique ID of the order.

#### Response (Success - 200 OK)
```json
{
  "order_id": "string (UUID)",
  "status": "PENDING | PROCESSING | COMPLETED | FAILED",
  "items": [
    {
      "sku": "string",
      "quantity": "integer"
    }
  ],
  "created_at": "datetime (ISO 8601)",
  "updated_at": "datetime (ISO 8601)"
}
```

#### Response (Not Found - 404 Not Found)
```json
{
  "detail": "Order not found"
}
```

---

### 3. Health Check
**GET `/health`**

Returns the status of the service.

#### Response (Success - 200 OK)
```json
{
  "status": "healthy"
}
```
