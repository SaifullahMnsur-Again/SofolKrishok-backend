from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from marketplace.models import Product, Order, OrderItem
from finance.models import Transaction

User = get_user_model()


class MarketplaceTestCase(APITestCase):
    """
    Test suite for e-commerce logic, query filters, foreign key operations,
    atomic stock decrement, order cancellation, and custom model properties.
    """

    def setUp(self):
        # Create users
        self.password = "SecurePassword123"
        
        # Staff user to create/manage products
        self.staff_user = User.objects.create_user(
            username="sales_manager",
            email="sales@example.com",
            password=self.password,
            role="sales_team_lead"
        )
        
        # Customer user
        self.customer = User.objects.create_user(
            username="customer_farmer",
            email="customer@example.com",
            password=self.password,
            role="farmer"
        )

        # Create dummy products
        self.fertilizer = Product.objects.create(
            name="Super Nitrogen Urea",
            description="High quality nitrogen fertilizer",
            category=Product.Category.FERTILIZER,
            price=1200.00,
            discount_price=1050.00,
            stock_quantity=50,
            unit="bag",
            status=Product.Status.ACTIVE,
            created_by=self.staff_user
        )

        self.seeds = Product.objects.create(
            name="BRRI Dhan 28 Rice Seeds",
            description="Premium quality rice seeds",
            category=Product.Category.SEEDS,
            price=450.00,
            stock_quantity=100,
            unit="kg",
            status=Product.Status.ACTIVE,
            created_by=self.staff_user
        )

        self.draft_product = Product.objects.create(
            name="Draft Product",
            description="Not yet active",
            category=Product.Category.OTHER,
            price=100.00,
            stock_quantity=10,
            unit="piece",
            status=Product.Status.DRAFT,
            created_by=self.staff_user
        )

        # Retrieve paths
        self.product_list_url = reverse('product-list')
        self.order_list_url = reverse('order-list')

    def test_product_list_filtering(self):
        """Verifies listing active products and filtering by category."""
        refresh = RefreshToken.for_user(self.customer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        # 1. Browse active products (Draft products must be excluded for non-staff)
        response = self.client.get(self.product_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify count of results (fertilizer and seeds are active, draft is not)
        self.assertEqual(response.data["count"], 2)

        # 2. Filter products by category
        filter_response = self.client.get(f"{self.product_list_url}?category={Product.Category.FERTILIZER}")
        self.assertEqual(filter_response.status_code, status.HTTP_200_OK)
        self.assertEqual(filter_response.data["count"], 1)
        self.assertEqual(filter_response.data["results"][0]["name"], self.fertilizer.name)

    def test_create_order_atomic_stock_decrement(self):
        """Verifies order creation, foreign key relationship linking, and atomic stock decrement."""
        refresh = RefreshToken.for_user(self.customer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        order_data = {
            "shipping_address": "House 45, Road 2, Rajshahi",
            "notes": "Deliver by Friday morning",
            "order_items": [
                {"product": self.fertilizer.id, "quantity": 5},
                {"product": self.seeds.id, "quantity": 10}
            ]
        }

        # Check initial stocks
        self.assertEqual(self.fertilizer.stock_quantity, 50)
        self.assertEqual(self.seeds.stock_quantity, 100)

        response = self.client.post(self.order_list_url, order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify order was saved to database
        order_id = response.data["id"]
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.customer, self.customer)
        
        # Verify order total: (5 * 1050.00) + (10 * 450.00) = 5250.00 + 4500.00 = 9750.00
        self.assertEqual(float(order.total_amount), 9750.00)

        # Verify atomic stock decrement
        self.fertilizer.refresh_from_db()
        self.seeds.refresh_from_db()
        self.assertEqual(self.fertilizer.stock_quantity, 45)
        self.assertEqual(self.seeds.stock_quantity, 90)

        # Verify OrderItems are linked correctly (FK operation check)
        self.assertEqual(order.items.count(), 2)
        item1 = order.items.get(product=self.fertilizer)
        self.assertEqual(item1.quantity, 5)
        self.assertEqual(float(item1.price_at_purchase), 1050.00)

    def test_order_creation_insufficient_stock(self):
        """Verifies that placing an order for more than available stock fails and rolls back."""
        refresh = RefreshToken.for_user(self.customer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        order_data = {
            "shipping_address": "Rajshahi",
            "order_items": [
                {"product": self.fertilizer.id, "quantity": 60}  # Stock is only 50
            ]
        }

        response = self.client.post(self.order_list_url, order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("Insufficient stock", response.data["error"])

        # Verify stock remains unchanged (rolled back)
        self.fertilizer.refresh_from_db()
        self.assertEqual(self.fertilizer.stock_quantity, 50)

    def test_order_cancellation_restores_stock_and_refunds(self):
        """Verifies that customer cancelling an order restores product stock and initiates ledger refund."""
        refresh = RefreshToken.for_user(self.customer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        # 1. Place order
        order = Order.objects.create(
            customer=self.customer,
            shipping_address="Rajshahi",
            total_amount=1050.00,
            status=Order.Status.PENDING
        )
        OrderItem.objects.create(
            order=order,
            product=self.fertilizer,
            quantity=2,
            price_at_purchase=1050.00
        )
        # Manually decrement stock for SETUP (replicating order placement)
        self.fertilizer.stock_quantity = 48
        self.fertilizer.save()

        # 2. Simulate completed debit transaction for order
        debit_txn = Transaction.objects.create(
            user=self.customer,
            type=Transaction.Type.DEBIT,
            status=Transaction.Status.COMPLETED,
            amount=2100.00,
            description=f"Payment for Order #{order.id}",
            reference_id="TXN12345",
            order=order
        )

        # 3. Call cancel action via PATCH
        cancel_url = reverse('order-detail', kwargs={'pk': order.id})
        cancel_data = {"status": Order.Status.CANCELLED}
        response = self.client.patch(cancel_url, cancel_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 4. Verify stock is restored
        self.fertilizer.refresh_from_db()
        self.assertEqual(self.fertilizer.stock_quantity, 50) # restored from 48 to 50

        # 5. Verify transaction state updates and refund entry in ledger
        debit_txn.refresh_from_db()
        self.assertEqual(debit_txn.status, Transaction.Status.REFUNDED)

        refund_txn = Transaction.objects.filter(
            user=self.customer,
            type=Transaction.Type.CREDIT,
            status=Transaction.Status.COMPLETED,
            order=order
        ).first()
        self.assertIsNotNone(refund_txn)
        self.assertEqual(float(refund_txn.amount), 2100.00)
        self.assertEqual(refund_txn.reference_id, "REF-TXN12345")

    def test_order_item_custom_property_subtotal(self):
        """Unit test for the subtotal custom model property on OrderItem."""
        order = Order.objects.create(
            customer=self.customer,
            total_amount=0.00,
            status=Order.Status.PENDING
        )
        item = OrderItem(
            order=order,
            product=self.fertilizer,
            quantity=3,
            price_at_purchase=1050.00
        )
        # Assert subtotal matches quantity * price_at_purchase
        self.assertEqual(float(item.subtotal), 3150.00)
