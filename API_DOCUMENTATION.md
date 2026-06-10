# SofolKrishok API Documentation

**Base URL:** `http://localhost:8000/api` (development)  
**Production:** `/api` (with reverse proxy at root)

This document provides a comprehensive guide to the SofolKrishok unified REST API, detailing the purpose, sequence of calls, parameters, request bodies, and responses for every endpoint.

---

## Table of Contents

1. [Authentication & User Management](#1-authentication--user-management)
2. [Farming Management](#2-farming-management)
3. [AI Engine & ML Hub](#3-ai-engine--ml-hub)
4. [Marketplace](#4-marketplace)
5. [Consultations](#5-consultations)
6. [Finance & Billing](#6-finance--billing)

---

## 1. Authentication & User Management
**Audience:** Both (Farmers & Staff)

All protected endpoints require a valid JWT Bearer token in the `Authorization` header: `Authorization: Bearer <access_token>`.

### Typical Sequence of Calls
1. **POST** `/auth/login/` to obtain `access` and `refresh` tokens.
2. Store tokens in local storage.
3. Attach `Authorization: Bearer <access_token>` to all subsequent requests.
4. When access token expires (401 response), call **POST** `/auth/token/refresh/` with the refresh token to get a new access token.

### 1.1 Register User
- **POST** `/auth/register/`
- **Purpose:** Create a new user account (Farmer or Staff).
- **Request Body:**
  ```json
  {
    "username": "newuser",
    "email": "user@example.com",
    "password": "SecurePass123",
    "password_confirm": "SecurePass123",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+8801234567890",
    "role": "farmer",
    "preferred_language": "bengali"
  }
  ```
- **Response:** `201 Created` - Returns the created user object.

### 1.2 Login (Token Obtain)
- **POST** `/auth/login/`
- **Purpose:** Authenticate and obtain JWT access and refresh tokens.
- **Request Body:**
  ```json
  {
    "username": "user@example.com",
    "password": "SecurePass123"
  }
  ```
- **Response:** `200 OK`
  ```json
  {
    "access": "eyJ0e...",
    "refresh": "eyJ0e...",
    "user": { "id": 1, "role": "farmer", "email": "..." }
  }
  ```

### 1.3 Refresh Token
- **POST** `/auth/token/refresh/`
- **Purpose:** Obtain a new access token using a valid refresh token.
- **Request Body:** `{ "refresh": "eyJ0e..." }`
- **Response:** `200 OK` - `{ "access": "new_eyJ0e..." }`

### 1.4 Get/Update Profile
- **GET/PATCH** `/auth/profile/`
- **Purpose:** View or update the currently authenticated user's profile.
- **Response (GET):** `200 OK`
  ```json
  {
    "id": 1,
    "username": "johndoe",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "farmer",
    "phone": "+880...",
    "address": "Dhaka",
    "preferred_language": "bengali",
    "zone": "Dhaka",
    "avatar_url": "/media/avatars/john.jpg"
  }
  ```
- **Request Body (PATCH):** Provide any editable fields (e.g., `phone`, `first_name`, `address`).

### 1.5 Avatar Management
- **POST / DELETE** `/auth/avatar/`
- **Purpose:** Upload or delete the user's profile picture.
- **Request (POST):** `multipart/form-data` with key `avatar`.
- **Response:** `200 OK`

### 1.6 Change Password
- **POST** `/auth/change-password/`
- **Purpose:** Update user password securely.
- **Request Body:**
  ```json
  {
    "current_password": "OldPass123",
    "new_password": "NewPass456",
    "confirm_password": "NewPass456"
  }
  ```
- **Response:** `200 OK` - Password updated successfully.

### 1.7 User Management (Staff/Admin)
- **GET** `/auth/users/`
  - **Purpose:** List all users (Staff only).
- **GET/PATCH/DELETE** `/auth/manage/{id}/`
  - **Purpose:** Manage specific users (update roles, zone, etc.).
- **GET** `/auth/manage/{id}/activity/`
  - **Purpose:** View user's recent system activity (logins, actions).

### 1.8 Audit Logs
- **GET** `/auth/audit/`
- **Purpose:** View system-wide audit logs tracking user actions like role changes, account creation, deletions, and administrative operations. (Manager roles only).

### 1.9 Notifications
- **GET** `/auth/notifications/` - List user's notifications.
- **POST** `/auth/notifications/` - Create a notification (Staff only).
- **POST** `/auth/notifications/{id}/mark_read/` - Mark as read.

---

## 2. Farming Management
**Audience:** Farmer

CRUD operations for managing agricultural land parcels, tracking crop cycles, phenophases, and activity logs.

### Typical Sequence of Calls
1. **GET** `/farming/crops/` - Farmer retrieves the global list of supported crops.
2. **POST** `/farming/lands/` - Farmer creates a new Land Parcel profile.
3. **POST** `/farming/tracks/` - Farmer starts a new crop growing season on that land, providing the crop ID.
3. **POST** `/farming/tracks/{id}/activities/` to log watering, fertilizing, etc.
4. **GET** `/farming/lands/{id}/history/` to view the comprehensive audit trail.

### 2.1 Land Parcels
- **GET** `/farming/lands/` - List authenticated user's land parcels.
- **POST** `/farming/lands/` - Register new land.
  **Request Body:**
  ```json
  {
    "name": "North Field",
    "location": "Rajshahi Village",
    "latitude": 24.3745,
    "longitude": 88.5971,
    "area_acres": 5.5,
    "soil_type": "loamy",
    "notes": "Good irrigation"
  }
  ```
- **GET/PUT/PATCH/DELETE** `/farming/lands/{id}/` - Manage specific land parcel.
- **GET** `/farming/lands/{id}/history/` - View complete land & crop history including previous values and changes.

### 2.2 Crop Tracks (Seasons)
- **GET** `/farming/tracks/` - List active and past crop tracks.
- **POST** `/farming/tracks/` - Start a new crop season.
  - **Request Body:**
  ```json
  {
    "land": 12,
    "crop": 5,
    "season": "Winter 2026",
    "planted_date": "2026-01-15"
  }
  ```
- **GET/PUT/PATCH/DELETE** `/farming/tracks/{id}/` - Manage specific crop track.
- **GET/POST** `/farming/tracks/{id}/activities/` - Log farming activities.
  **POST Body:**
  ```json
  {
    "activity_type": "irrigation",
    "notes": "Applied 50L water",
    "occurred_at": "2026-05-15T10:00:00Z"
  }
  ```
  *Note: Logging a `harvest` activity automatically updates the track's actual_harvest_date and status.*

### 2.3 Crop Registry
- **GET** `/farming/crops/` - List all crops available in the system. Farmers see public crops and their own suggestions. Staff see all crops.
- **POST** `/farming/crops/` - Suggest a new crop (if farmer) or create an approved crop (if staff). Requires `name_en` and `name_bn`.
- **PATCH** `/farming/crops/{id}/` - Staff only. Update crop details and approve farmer suggestions.

### 2.4 Crop Stages
- **GET/POST** `/farming/stages/` - Manage specific growth phases (e.g. Vegetative, Flowering).
- **GET/PUT/PATCH/DELETE** `/farming/stages/{id}/`

### 2.4 Farming Cycles
- **GET/POST** `/farming/cycles/` - Manage complete farming cycles with financial tracking (revenue, investment, ROI).
- **GET/PUT/PATCH/DELETE** `/farming/cycles/{id}/`

### 2.5 Weather
- **GET** `/farming/weather/?lat=24.3745&lon=88.6042&days=3`
- **Purpose:** Get weather forecast for farming operations. Defaults to the user's first land parcel coordinates if `lat`/`lon` are not provided.

---

## 3. AI Engine & ML Hub
**Audience:** Both

API for interacting with generative AI, computer vision models, and natural language processing.

### 3.1 Chat Sessions
- **GET/POST** `/ai/chat-sessions/` - List or create memory-aware chat sessions.
  **POST Body:** `{ "title": "Rice Disease Advice" }`
- **GET/DELETE** `/ai/chat-sessions/{id}/` - Retrieve session history or delete it.

### 3.2 Gemini Chat
- **POST** `/ai/gemini-chat/`
- **Purpose:** Send a message to the Gemini AI within a specific session.
- **Request Body:**
  ```json
  {
    "message": "What fertilizer is best for sandy soil?",
    "session_id": 1
  }
  ```
- **Response:**
  ```json
  {
    "response": "For sandy soils, use...",
    "session_id": 1,
    "history": [...]
  }
  ```

### 3.3 Disease Detection
- **POST** `/ai/disease-detect/`
- **Purpose:** Detect crop diseases from images.
- **Request (multipart/form-data):** `image` (File), `crop_type` (String).
- **Response:** `200 OK`
  ```json
  {
    "disease": "Leaf Blight",
    "confidence": 0.95,
    "treatment_recommendation": "Apply fungicide XYZ..."
  }
  ```

### 3.4 Soil Classification
- **POST** `/ai/soil-classify/`
- **Purpose:** Classify soil type from an image.
- **Request (multipart/form-data):** `image` (File).
- **Response:** `200 OK`
  ```json
  {
    "soil_type": "Loamy",
    "confidence": 0.88,
    "ph_estimate": 6.5
  }
  ```

### 3.5 Voice Commands
- **POST** `/ai/voice-command/`
- **Purpose:** Parse natural language voice text into actionable UI intents.
- **Request Body:** `{ "text": "show me my pending orders" }`
- **Response:** `200 OK`
  ```json
  {
    "intent": "NAVIGATE",
    "target": "/orders?status=pending",
    "confidence": 0.98
  }
  ```

### 3.6 AI Models Management (Staff Only)
- **GET/POST** `/ai/models/` - List or upload new ML model artifacts (`.tflite`, `.h5`).
- **PATCH** `/ai/models/{id}/` - Partially update an existing model artifact (e.g., change its name, active status, or replace file).
- **POST** `/ai/models/{id}/activate/` - Set a model as the active version for its crop and operation.
- **GET** `/ai/models/inventory/` - Returns the full structured snapshot of all disease and soil models along with Gemini API configurations for the Staff Model Hub UI.
- **GET** `/ai/model-usage/` - View telemetry and usage stats.
- **GET** `/ai/active-disease-crops/` - List crops that currently have an active disease detection model available.
- **GET/PATCH** `/ai/settings/gemini/` - Manage Gemini API Key and Model configurations.

---

## 4. Marketplace
**Audience:** Both

E-commerce platform for agricultural products.

### Typical Sequence of Calls
1. **GET** `/marketplace/products/` - Farmer browses available products.
2. **POST** `/marketplace/orders/` - Farmer creates an order with multiple items. Stock is atomically decremented.
3. **POST** `/finance/checkout/` - Farmer pays for the order via the Finance module.
4. Staff uses **PATCH** `/marketplace/orders/{id}/` to move order status to `shipped` or `delivered`.

### 4.1 Products
- **GET** `/marketplace/products/`
  - **Query Params:** `?category=fertilizer`
  - **Response:** Paginated list of active products.
- **GET** `/marketplace/products/{id}/` - Get product details.
- **POST/PUT/PATCH/DELETE** `/marketplace/products/` (Staff only) - Manage product inventory, set `stock_quantity`, `price`, `discount_price`.

### 4.2 Orders
- **GET** `/marketplace/orders/` - List orders (Customers see own, Staff see all).
- **POST** `/marketplace/orders/`
  - **Purpose:** Place a new order.
  - **Request Body:**
    ```json
    {
      "shipping_address": "123 Farm Road",
      "notes": "Deliver in the morning",
      "order_items": [
        { "product": 5, "quantity": 2 },
        { "product": 12, "quantity": 1 }
      ]
    }
    ```
  - **Response:** `201 Created` - Returns created order with `total_amount` calculated and stock decremented.
- **PATCH** `/marketplace/orders/{id}/`
  - **Purpose:** Update status.
  - **Request Body:** `{ "status": "shipped" }`
  - *Note: If a customer cancels an order (`status: "cancelled"`), stock is restored and a refund transaction is automatically generated.*

---

## 5. Consultations
**Audience:** Both

Scheduling and live sessions with agricultural experts.

### Typical Sequence of Calls
1. **Staff** creates shifts using **POST** `/consultation/slots/`.
2. **Farmer** books an available slot using **POST** `/consultation/tickets/book/`.
3. At the scheduled time, **Expert** calls **POST** `/consultation/tickets/{id}/start_session/`.
4. When finished, either party calls **POST** `/consultation/tickets/{id}/complete_session/`.

### 5.1 Consultation Slots
- **GET** `/consultation/slots/` - List slots. Query params: `?date=2026-05-10&available=true`
- **POST** `/consultation/slots/` (Staff only)
  - **Purpose:** Generate 20-minute consultation slots automatically for a specific shift.
  - **Request Body:**
    ```json
    {
      "expert": 4,
      "date": "2026-05-15",
      "shift": "morning"
    }
    ```
- **GET** `/consultation/slots/coverage/` (Staff only) - Analytics on slot utilization and expert loads.

### 5.2 Tickets (Bookings)
- **GET** `/consultation/tickets/` - List bookings.
- **POST** `/consultation/tickets/book/`
  - **Purpose:** Farmer books an available slot.
  - **Request Body:**
    ```json
    {
      "slot_id": 42,
      "notes": "My rice plants are turning yellow."
    }
    ```
- **POST** `/consultation/tickets/{id}/start_session/`
  - **Purpose:** Expert marks session as in-progress. Sends notification to farmer.
- **POST** `/consultation/tickets/{id}/complete_session/`
  - **Purpose:** Close the consultation room.
  - **Request Body (Expert):** `{ "expert_summary": "Identified nitrogen deficiency. Advised urea." }`

---

## 6. Finance & Billing
**Audience:** Both

Payment processing, subscription plans, and unified financial ledger.

### 6.1 Subscription Plans
- **GET** `/finance/plans/` - List available tier plans (Basic, Premium, Enterprise).
- **POST/PUT/PATCH/DELETE** `/finance/plans/` (Staff only) - Manage plans.
- **GET** `/finance/subscription/` - View the authenticated user's current active subscription.

### 6.2 Checkout
- **POST** `/finance/checkout/`
  - **Purpose:** Initiate an external payment gateway session for an order, consultation, or subscription.
  - **Request Body:**
    ```json
    {
      "order_id": 105,
      "description": "Payment for Order #105"
    }
    ```
  - **Response:** `200 OK`
    ```json
    {
      "payment_url": "https://sandbox.sslcommerz.com/...",
      "reference_id": "TXN123456"
    }
    ```

### 6.3 Payment IPN Callback
- **POST** `/finance/payment/callback/`
  - **Purpose:** Webhook endpoint for SSLCommerz/payment gateway to send asynchronous payment success/failure notifications. Updates Transaction status securely.

### 6.4 Ledger / Transactions
- **GET** `/finance/ledger/`
  - **Purpose:** View user's financial history (debits, credits, refunds).
  - **Response:** Paginated list of transactions including `amount`, `status`, `reference_id`, and `created_at`.
