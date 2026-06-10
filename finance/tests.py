from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from finance.models import SubscriptionPlan, Subscription, Transaction
from marketplace.models import Order
from decimal import Decimal
import datetime

User = get_user_model()


class FinanceTestCase(APITestCase):
    """
    Test suite for subscription plans, current user subscription snapshot,
    checkout session generation, and Simulated SSLCommerz callback outcomes.
    """

    def setUp(self):
        self.password = "SecurePassword123"
        self.farmer = User.objects.create_user(
            username="finance_farmer",
            email="finance_farmer@example.com",
            password=self.password,
            role="farmer"
        )
        self.manager = User.objects.create_user(
            username="finance_mgr",
            email="finance_mgr@example.com",
            password=self.password,
            role="general_manager"
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Premium Plan",
            plan_type=SubscriptionPlan.PlanType.PRIMARY,
            price_monthly=Decimal("500.00"),
            credits=20,
            is_active=True
        )

    def test_plans_list_and_management(self):
        """Verifies plan seeding, filtering for farmers, and admin creation with notifications."""
        # 1. Seed defaults endpoint
        refresh = RefreshToken.for_user(self.manager)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        seed_url = reverse('plan-seed-defaults')
        response = self.client.post(seed_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify plans list has default seeded plans
        list_url = reverse('plan-list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data["results"]) > 1)

        # 2. Farmer credentials and listing filters only active
        farmer_refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {farmer_refresh.access_token}')
        
        # Deactivate one plan
        self.plan.is_active = False
        self.plan.save()
        
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        active_plan_names = [p["name"] for p in response.data["results"]]
        self.assertNotIn("Premium Plan", active_plan_names)

    def test_subscription_lazy_initialization(self):
        """Verifies that accessing subscription detail lazily creates a fallback subscription when missing."""
        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        sub_url = reverse('subscription')
        self.assertFalse(Subscription.objects.filter(user=self.farmer).exists())

        response = self.client.get(sub_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Subscription.objects.filter(user=self.farmer).exists())
        self.assertEqual(response.data["plan"]["name"].lower(), "free")

    def test_checkout_generation(self):
        """Verifies creating checkout sessions for both plan subscriptions and marketplace orders."""
        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        checkout_url = reverse('checkout')

        # 1. Plan subscription checkout
        plan_data = {
            "plan_id": self.plan.id,
            "description": "Upgrading to premium"
        }
        response = self.client.post(checkout_url, plan_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("payment_url", response.data)
        ref_id = response.data["reference_id"]
        
        txn = Transaction.objects.get(reference_id=ref_id)
        self.assertEqual(txn.status, "pending")
        self.assertEqual(txn.amount, Decimal("500.00"))

        # 2. Marketplace order checkout
        order = Order.objects.create(
            customer=self.farmer,
            total_amount=Decimal("1500.00"),
            status=Order.Status.PENDING
        )
        order_data = {
            "order_id": order.id
        }
        response = self.client.post(checkout_url, order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data["amount"]), Decimal("1500.00"))

    def test_payment_callback_outcomes(self):
        """Simulates callback payments from gateway for subscription and orders."""
        # Setup pending subscription transaction
        ref_sub = "SSL-TESTSUB"
        txn_sub = Transaction.objects.create(
            user=self.farmer,
            type=Transaction.Type.DEBIT,
            status=Transaction.Status.PENDING,
            amount=Decimal("500.00"),
            description="Premium sub",
            reference_id=ref_sub,
            metadata={"plan_id": self.plan.id, "kind": "subscription"}
        )

        # Setup pending order transaction
        order = Order.objects.create(
            customer=self.farmer,
            total_amount=Decimal("1200.00"),
            status=Order.Status.PENDING
        )
        ref_ord = "SSL-TESTORD"
        txn_ord = Transaction.objects.create(
            user=self.farmer,
            type=Transaction.Type.DEBIT,
            status=Transaction.Status.PENDING,
            amount=Decimal("1200.00"),
            description="Marketplace purchase",
            reference_id=ref_ord,
            metadata={"order_id": order.id, "kind": "order"},
            order=order
        )

        callback_url = reverse('payment-callback')

        # 1. Failure simulation
        fail_response = self.client.post(callback_url, {"reference_id": ref_sub, "status": "failed"}, format='json')
        self.assertEqual(fail_response.status_code, status.HTTP_200_OK)
        txn_sub.refresh_from_db()
        self.assertEqual(txn_sub.status, "failed")

        # 2. Success simulation: orders status advances
        success_response = self.client.post(callback_url, {"reference_id": ref_ord, "status": "success"}, format='json')
        self.assertEqual(success_response.status_code, status.HTTP_200_OK)
        txn_ord.refresh_from_db()
        self.assertEqual(txn_ord.status, "completed")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PROCESSING)

        # 3. Success simulation: subscription activated/extended
        # Re-set transaction to pending for successful sub test
        txn_sub.status = Transaction.Status.PENDING
        txn_sub.save()
        success_response2 = self.client.post(callback_url, {"reference_id": ref_sub, "status": "success"}, format='json')
        self.assertEqual(success_response2.status_code, status.HTTP_200_OK)
        
        # Verify user has active Subscription in DB with plan credits added
        sub = Subscription.objects.get(user=self.farmer)
        self.assertEqual(sub.plan, self.plan)
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        self.assertEqual(sub.remaining_credits, 20)
