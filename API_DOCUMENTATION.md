# SofolKrishok API Documentation

**Base URL:** `http://localhost:8000/api` (development)  
**Production:** `/api` (with reverse proxy at root)

---

## Table of Contents

1. [Authentication](#authentication)
2. [Farming Management](#farming-management)
3. [AI Engine](#ai-engine)
4. [Marketplace](#marketplace)
5. [Consultations](#consultations)
6. [Finance & Billing](#finance--billing)
7. [Error Handling](#error-handling)

---

## Authentication

All endpoints except registration and login require a valid JWT Bearer token in the `Authorization` header:

```
Authorization: Bearer {access_token}
```

### Swagger Authorization Setup

Use this flow in Swagger UI:

1. Call `POST /auth/login/` to get both `access` and `refresh` tokens.
2. Click Authorize and set `Bearer` as: `Bearer {access_token}`.
3. Call protected endpoints using the access token.
4. When access token expires, call `POST /auth/token/refresh/` with:

```json
{
  "refresh": "{refresh_token}"
}
```

5. Replace the Bearer token in Swagger Authorize with the new access token.

### Endpoint Audience Segmentation

Audience labels are shown in endpoint descriptions:

- `Audience: Farmer` - Intended for farmer workflows
- `Audience: Staff` - Staff/manager/operations only
- `Audience: Both` - Available to both staff and farmers (role rules may still vary)

### Register User
- **POST** `/auth/register/`
- **Roles:** farmer, sales, service, expert, sales_team_lead, sales_team_member, service_team_lead, service_team_member, site_engineer, branch_manager, general_manager
- **Request:**
  ```json
  {
    "username": "newuser",
    "email": "user@example.com",
    "password": "SecurePass123",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+8801234567890",
    "role": "farmer",
    "zone": "Rajshahi",
    "language": "bengali"
  }
  ```
- **Response:** `201 Created` - User profile with JWT tokens

### Login
- **POST** `/auth/login/`
- **Request:**
  ```json
  {
    "username": "user@example.com",
    "password": "SecurePass123"
  }
  ```
- **Response:** `200 OK`
  ```json
  {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "user": { /* user profile */ }
  }
  ```

### Refresh Token
- **POST** `/auth/token/refresh/`
- **Request:**
  ```json
  {
    "refresh": "{refresh_token}"
  }
  ```
- **Response:** `200 OK` - New access token

### Get Current Profile
- **GET** `/auth/profile/`
- **Auth Required:** Yes

### Update Profile
- **PUT/PATCH** `/auth/profile/`
- **Auth Required:** Yes
- **Request:**
  ```json
  {
    "first_name": "Jane",
    "language": "english",
    "zone": "Sylhet"
  }
  ```

### Upload Avatar
- **POST** `/auth/avatar/`
- **Auth Required:** Yes
- **Content-Type:** `multipart/form-data`
- **Body:** Form with `avatar` field (JPEG/PNG, max 5MB)

### Change Password
- **POST** `/auth/change-password/`
- **Auth Required:** Yes
- **Request:**
  ```json
  {
    "current_password": "OldPass123",
    "new_password": "NewPass456",
    "confirm_password": "NewPass456"
  }
  ```

---

## Farming Management

### Land Parcels

#### List/Create Land
- **GET/POST** `/farming/lands/`
- **Auth Required:** Yes
- **GET Response:** Paginated list of user's land parcels
- **POST Request:**
  ```json
  {
    "name": "North Field",
    "location": "Rajshahi District",
    "latitude": "24.3745",
    "longitude": "88.5971",
    "area_acres": "5.5",
    "soil_type": "loamy",
    "notes": "Recently irrigated"
  }
  ```

#### Get/Update/Delete Land
- **GET/PUT/PATCH/DELETE** `/farming/lands/{id}/`
- **Auth Required:** Yes
- **Permissions:** Owner only

#### Land History
- **GET** `/farming/lands/{id}/history/`
- **Returns:** Immutable modification history for the land parcel

### Crop Tracks

#### List/Create Crop Track
- **GET/POST** `/farming/tracks/`
- **Auth Required:** Yes
- **POST Request:**
  ```json
  {
    "land": 1,
    "crop_name": "Rice",
    "crop_type": "rice",
    "sowing_date": "2026-04-15",
    "expected_harvest": "2026-07-15",
    "quantity_kg": "500",
    "seed_variety": "BR29",
    "notes": "Organic farming"
  }
  ```

#### Track Activities (Irrigation, Fertilization, Pesticide, Harvest)
- **GET/POST** `/farming/tracks/{id}/activities/`
- **POST Request:**
  ```json
  {
    "activity_type": "irrigation",
    "date": "2026-05-10",
    "quantity": "50",
    "unit": "liter",
    "notes": "Second irrigation round"
  }
  ```

### Farming Cycles (Seasons)

#### List/Create Cycles
- **GET/POST** `/farming/cycles/`
- **Auth Required:** Yes
- **POST Request:**
  ```json
  {
    "land": 1,
    "season": "2026-summer",
    "status": "active",
    "start_date": "2026-04-01",
    "end_date": "2026-09-30",
    "crop_type": "rice",
    "yield_kg": null,
    "investment_taka": "25000",
    "revenue_taka": null,
    "notes": "Summer rice cultivation"
  }
  ```

#### Cycle Modification History
- **GET** `/farming/cycles/{id}/history/`
- **Returns:** Complete audit trail of all cycle changes

### Weather

#### Get Weather Forecast
- **GET** `/farming/weather/?lat=24.3745&lon=88.5971&days=7`
- **Auth Required:** Yes
- **Response:**
  ```json
  {
    "location": "Rajshahi",
    "forecasts": [
      {
        "date": "2026-04-30",
        "temp_min": "28",
        "temp_max": "35",
        "humidity": "75",
        "rainfall_mm": "5",
        "condition": "Partly Cloudy",
        "irrigation_advice": "Water if soil is dry"
      }
    ]
  }
  ```

---

## AI Engine

### Chat Sessions

#### Create Session
- **POST** `/ai/chat-sessions/`
- **Auth Required:** Yes
- **Request:**
  ```json
  {
    "title": "Rice Farming Questions",
    "crop_context": "rice",
    "land": 1
  }
  ```

#### Send Message
- **POST** `/ai/gemini-chat/`
- **Auth Required:** Yes
- **Request:**
  ```json
  {
    "session_id": 5,
    "message": "How do I prevent rice blast disease?",
    "land_id": 1,
    "crop_type": "rice"
  }
  ```
- **Response:**
  ```json
  {
    "session_id": 5,
    "user_message": "...",
    "ai_response": "Rice blast is caused by the fungus Pyricularia oryzae...",
    "timestamp": "2026-04-30T10:30:00Z"
  }
  ```

### Disease Detection

#### Detect Disease
- **POST** `/ai/disease-detect/`
- **Content-Type:** `multipart/form-data`
- **Auth Required:** Yes
- **Request:**
  ```
  image: <JPEG/PNG file>
  crop_type: rice
  land_id: 1
  ```
- **Response:**
  ```json
  {
    "disease_detected": "Rice Blast",
    "confidence": "95%",
    "severity": "moderate",
    "treatment": "Apply fungicide XYZ...",
    "similar_diseases": ["Brown Spot", "Leaf Smut"],
    "image_url": "/media/disease_scans/..."
  }
  ```

### Soil Classification

#### Classify Soil
- **POST** `/ai/soil-classify/`
- **Content-Type:** `multipart/form-data`
- **Auth Required:** Yes
- **Request:**
  ```
  image: <soil sample photo>
  land_id: 1
  ```
- **Response:**
  ```json
  {
    "soil_type": "loamy",
    "texture": "sandy-clay-loam",
    "ph": "7.2",
    "fertility_rating": "high",
    "recommended_crops": ["rice", "wheat", "vegetables"],
    "fertilizer_recommendations": {
      "nitrogen": "100 kg/acre",
      "phosphorus": "50 kg/acre",
      "potassium": "40 kg/acre"
    }
  }
  ```

### AI Model Management

#### List AI Models
- **GET** `/ai/models/`
- **Auth Required:** Yes
- **Response:** Paginated list of available AI models with status

#### Model Usage History
- **GET** `/ai/model-usage/?service=disease_detection&start=2026-04-01&end=2026-04-30`
- **Auth Required:** Yes
- **Response:** Usage analytics with charts data

---

## Marketplace

### Products

#### List Products
- **GET** `/marketplace/products/?category=seeds&search=rice`
- **Auth Required:** No (browse only) / Yes (for orders)
- **Response:**
  ```json
  {
    "count": 150,
    "next": "/marketplace/products/?page=2",
    "results": [
      {
        "id": 42,
        "name": "BR29 Rice Seeds",
        "category": "seeds",
        "price_taka": "500",
        "stock_quantity": "100",
        "description": "High-yielding rice variety",
        "image_url": "/media/products/...",
        "vendor": "Green Seeds Ltd"
      }
    ]
  }
  ```

#### Get Product Details
- **GET** `/marketplace/products/{id}/`
- **Auth Required:** No

### Orders

#### Create Order
- **POST** `/marketplace/orders/`
- **Auth Required:** Yes
- **Request:**
  ```json
  {
    "product": 42,
    "quantity": 5,
    "delivery_address": "Village XYZ, Rajshahi",
    "payment_method": "bkash"
  }
  ```

#### List Orders
- **GET** `/marketplace/orders/`
- **Auth Required:** Yes (user sees only their orders)
- **Response:** User's order history with statuses

#### Update Order Status
- **PATCH** `/marketplace/orders/{id}/`
- **Auth Required:** Yes (vendor/staff only)
- **Request:**
  ```json
  {
    "status": "shipped"
  }
  ```

---

## Consultations

### Consultation Slots

#### List Available Slots
- **GET** `/consultation/slots/?available=true&expert_role=agronomist`
- **Auth Required:** No (public view)
- **Response:**
  ```json
  {
    "count": 45,
    "results": [
      {
        "id": 8,
        "expert": "Dr. Karim Ahmed",
        "expert_role": "agronomist",
        "date": "2026-05-05",
        "time_start": "10:00",
        "time_end": "10:30",
        "mode": "video",
        "consultation_type": "crop_disease",
        "price_taka": "500",
        "is_available": true
      }
    ]
  }
  ```

### Tickets (Bookings)

#### Book Consultation
- **POST** `/consultation/tickets/book/`
- **Auth Required:** Yes
- **Request:**
  ```json
  {
    "slot": 8,
    "consultation_type": "crop_disease",
    "description": "My rice crop has brown spots"
  }
  ```

#### List User's Tickets
- **GET** `/consultation/tickets/`
- **Auth Required:** Yes
- **Response:** User's consultation bookings with session links

---

## Finance and Billing

### Subscription Plans

#### List Plans
- **GET** `/finance/plans/`
- **Auth Required:** No
- **Response:**
  ```json
  {
    "count": 3,
    "results": [
      {
        "id": 1,
        "name": "Starter",
        "plan_type": "primary",
        "price_monthly": "0",
        "credits": "0",
        "disease_detection_limit": "5",
        "ai_assistant_daily_limit": "20",
        "expert_appointment_limit": "0",
        "features": [
          "AI Disease Detection",
          "Soil Analysis",
          "Weather Forecast"
        ]
      }
    ]
  }
  ```

### Checkout

#### Initiate Payment
- **POST** `/finance/checkout/`
- **Auth Required:** Yes
- **Request:**
  ```json
  {
    "plan_id": 2,
    "payment_gateway": "sslcommerz",
    "currency": "BDT"
  }
  ```
- **Response:**
  ```json
  {
    "session_id": "62e7d29c-1234-5678",
    "checkout_url": "https://sandbox.sslcommerz.com/gwprocess/v4/gw.php?...",
    "total_amount": "299"
  }
  ```

### Transaction Ledger

#### View Billing History
- **GET** `/finance/ledger/?start_date=2026-04-01&end_date=2026-04-30`
- **Auth Required:** Yes
- **Response:**
  ```json
  {
    "count": 2,
    "results": [
      {
        "id": 15,
        "type": "subscription_charge",
        "amount_taka": "299",
        "date": "2026-04-15",
        "status": "completed",
        "description": "Farmer Pro - April 2026",
        "plan": "Farmer Pro"
      }
    ]
  }
  ```

---

## Error Handling

All errors follow this format:

```json
{
  "detail": "Error message",
  "errors": {
    "field_name": ["Field-specific error message"]
  }
}
```

### Common HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 204 | No Content - Success, no response body |
| 400 | Bad Request - Invalid parameters or validation error |
| 401 | Unauthorized - Missing or invalid authentication token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 409 | Conflict - Duplicate entry or business rule violation |
| 500 | Server Error - Internal server error |

### Authentication Errors

- **401 Unauthorized:** Missing or invalid token
  ```json
  {
    "detail": "Authentication credentials were not provided."
  }
  ```

- **403 Forbidden:** Insufficient permissions
  ```json
  {
    "detail": "You do not have permission to perform this action."
  }
  ```

### Validation Errors

- **400 Bad Request:** Invalid data
  ```json
  {
    "errors": {
      "email": ["Enter a valid email address."],
      "phone": ["Phone number must start with +880"]
    }
  }
  ```

---

## Pagination

List endpoints return paginated responses:

```json
{
  "count": 150,
  "next": "/api/endpoint/?page=2",
  "previous": null,
  "results": [/* items */]
}
```

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)
- `search`: Search term for filterable fields
- `ordering`: Sort field (prefix with `-` for descending)

---

## Searching and Filtering

Most list endpoints support filtering:

```
GET /farming/lands/?search=north&area_acres__gte=5
GET /marketplace/products/?category=seeds&price_taka__lte=1000
GET /finance/ledger/?status=completed&date__gte=2026-04-01
```

---

## WebSocket Endpoints (Real-time)

### Consultation Session
- **WS:** `/ws/consultation/{ticket_id}/`
- **Messages:** JSON-formatted chat messages between farmer and consultant

### Notifications
- **WS:** `/ws/notifications/`
- **Messages:** Real-time notification push events

---

## Testing Endpoints

**Quick Test Flow:**

```bash
# 1. Register
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testfarmer",
    "email": "test@example.com",
    "password": "Test@123456",
    "first_name": "Test",
    "last_name": "Farmer",
    "phone": "+8801234567890",
    "role": "farmer"
  }'

# 2. Login
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testfarmer",
    "password": "Test@123456"
  }'

# 3. Use access token
curl -X GET http://localhost:8000/api/auth/profile/ \
  -H "Authorization: Bearer {access_token}"
```

---

**Swagger UI:** http://localhost:8000/api/docs/  
**Schema (JSON):** http://localhost:8000/api/schema.json/

---

*Last Updated: April 29, 2026*  
*For issues or suggestions, contact: development@sofolkrishok.com*
