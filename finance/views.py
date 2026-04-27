from rest_framework import viewsets, permissions, generics
from rest_framework.decorators import action
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from .models import SubscriptionPlan, Subscription, Transaction
from .serializers import SubscriptionPlanSerializer, SubscriptionSerializer, TransactionSerializer
from users.models import Notification
from django.contrib.auth import get_user_model


User = get_user_model()


DEFAULT_PLANS = [
    {
        'name': 'Free',
        'plan_type': 'primary',
        'description': 'Free starter tier for learning and light usage.',
        'price_monthly': 0,
        'credits': 0,
        'disease_detection_limit': 8,
        'ai_assistant_daily_limit': 8,
        'expert_appointment_limit': 0,
        'market_prediction_limit': 5,
        'farming_suggestion_limit': 20,
        'discount_percent': 0,
        'features_json': [
            'Starter disease scanning',
            'Daily AI guidance basics',
            'Community knowledge base',
        ],
        'is_active': True,
    },
    {
        'name': 'Agontuk',
        'plan_type': 'primary',
        'description': 'Entry paid tier for seasonal and small-scale farmers.',
        'price_monthly': 299,
        'credits': 3,
        'disease_detection_limit': 35,
        'ai_assistant_daily_limit': 30,
        'expert_appointment_limit': 2,
        'market_prediction_limit': 25,
        'farming_suggestion_limit': 80,
        'discount_percent': 5,
        'features_json': [
            'Priority disease scans',
            'Faster assistant response lane',
            'Starter expert appointment access',
        ],
        'is_active': True,
    },
    {
        'name': 'Porompora',
        'plan_type': 'primary',
        'description': 'Advanced operating tier for family-run and legacy farms.',
        'price_monthly': 899,
        'credits': 14,
        'disease_detection_limit': 160,
        'ai_assistant_daily_limit': 130,
        'expert_appointment_limit': 10,
        'market_prediction_limit': 120,
        'farming_suggestion_limit': 300,
        'discount_percent': 12,
        'features_json': [
            'Extended seasonal planning tools',
            'Expanded agronomy advisory coverage',
            'Higher expert consultation capacity',
        ],
        'is_active': True,
    },
    {
        'name': 'Uddokta',
        'plan_type': 'primary',
        'description': 'Growth plan for agri-entrepreneurs and expanding farms.',
        'price_monthly': 599,
        'credits': 8,
        'disease_detection_limit': 90,
        'ai_assistant_daily_limit': 70,
        'expert_appointment_limit': 6,
        'market_prediction_limit': 70,
        'farming_suggestion_limit': 180,
        'discount_percent': 10,
        'features_json': [
            'Advanced disease confidence reports',
            'Expanded market trend coverage',
            'Higher expert support quota',
        ],
        'is_active': True,
        'is_featured': True,
    },
    {
        'name': 'Jomidar',
        'plan_type': 'primary',
        'description': 'Premium enterprise plan for large operations and teams.',
        'price_monthly': 1299,
        'credits': 22,
        'disease_detection_limit': 260,
        'ai_assistant_daily_limit': 220,
        'expert_appointment_limit': 18,
        'market_prediction_limit': 190,
        'farming_suggestion_limit': 420,
        'discount_percent': 15,
        'features_json': [
            'Team-level advisory operations',
            'High-frequency forecasting',
            'Premium expert allocation',
            'Operational analytics dashboard',
        ],
        'is_active': True,
    },
]


def ensure_default_plans():
    desired_names = {plan['name'] for plan in DEFAULT_PLANS}

    # Keep catalog concise by deactivating old seeded plans that are no longer offered.
    SubscriptionPlan.objects.exclude(name__in=desired_names).update(is_active=False)

    for plan in DEFAULT_PLANS:
        name = plan['name']
        defaults = {k: v for k, v in plan.items() if k != 'name'}
        SubscriptionPlan.objects.update_or_create(name=name, defaults=defaults)


@method_decorator(name='list', decorator=swagger_auto_schema(tags=['Finance']))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(tags=['Finance']))
@method_decorator(name='create', decorator=swagger_auto_schema(tags=['Finance']))
@method_decorator(name='update', decorator=swagger_auto_schema(tags=['Finance']))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(tags=['Finance']))
@method_decorator(name='destroy', decorator=swagger_auto_schema(tags=['Finance']))
class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """GET/POST /api/finance/plans/ — Manage subscription plans (GM only)."""
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        ensure_default_plans()
        # Leaders/managers see all, farmers see only active plans
        if self.request.user.role in ['general_manager', 'site_engineer', 'branch_manager', 'sales_team_lead', 'service_team_lead']:
            return SubscriptionPlan.objects.all()
        return SubscriptionPlan.objects.filter(is_active=True)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.offline_at = timezone.now()
        instance.save(update_fields=['is_active', 'offline_at'])

    def create(self, request, *args, **kwargs):
        notify_farmers = str(request.data.get('notify_farmers', 'false')).lower() in {'1', 'true', 'yes'}
        notification_message = (request.data.get('notification_message') or '').strip()
        notify_target = (request.data.get('notify_target') or 'all').strip().lower()
        target_zones_raw = request.data.get('target_zones') or ''

        payload = request.data.copy()
        payload.pop('notify_farmers', None)
        payload.pop('notification_message', None)
        payload.pop('notify_target', None)
        payload.pop('target_zones', None)

        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        if notify_farmers and notification_message:
            farmers = User.objects.filter(role='farmer')

            if notify_target == 'zone':
                target_zones = [z.strip() for z in str(target_zones_raw).split(',') if z.strip()]
                if target_zones:
                    farmers = farmers.filter(zone__in=target_zones)

            farmers = farmers.only('id')
            notifications = [
                Notification(
                    user=farmer,
                    title='New Subscription Plan Available',
                    message=notification_message,
                    notification_type='subscription',
                )
                for farmer in farmers
            ]
            if notifications:
                Notification.objects.bulk_create(notifications, batch_size=1000)

        return Response(serializer.data, status=201, headers=headers)

    @action(detail=False, methods=['post'], url_path='seed-defaults')
    @swagger_auto_schema(tags=['Finance'])
    def seed_defaults(self, request):
        ensure_default_plans()
        return Response({'status': 'ok', 'message': 'Default subscription tiers seeded.'})

    def check_permissions(self, request):
        super().check_permissions(request)
        if self.action not in ['list', 'retrieve']:
            if request.user.role not in ['general_manager', 'site_engineer']:
                self.permission_denied(request, message="Only General Managers can configure subscriptions.")


@method_decorator(name='get', decorator=swagger_auto_schema(tags=['Finance']))
class SubscriptionView(generics.RetrieveAPIView):
    """GET /api/finance/subscription/ — Get current user's subscription."""
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Ensure at least one plan exists to avoid crashes
        ensure_default_plans()

        plan = SubscriptionPlan.objects.filter(name__iexact='free').first()
        if not plan:
            plan = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly').first()
        if not plan:
            plan = SubscriptionPlan.objects.create(
                name="free",
                plan_type='primary',
                description="Fallback free tier",
                price_monthly=0,
                credits=0,
            )

        sub, created = Subscription.objects.get_or_create(
            user=self.request.user,
            defaults={
                'plan': plan,
                'remaining_credits': 0,
                'expires_at': timezone.now() + timedelta(days=3650),
            },
        )
        return sub


@method_decorator(name='list', decorator=swagger_auto_schema(tags=['Finance']))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(tags=['Finance']))
class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/finance/ledger/ — View transaction history."""
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['general_manager', 'site_engineer', 'branch_manager', 'sales_team_lead', 'service_team_lead']:
            return Transaction.objects.all()
        return Transaction.objects.filter(user=user)


from rest_framework.views import APIView
from rest_framework.response import Response
import uuid

class CheckoutView(APIView):
    """POST /api/finance/checkout/ — Initiate a checkout and return payment URL."""
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(tags=['Finance'])
    def post(self, request):
        amount = request.data.get('amount')
        description = request.data.get('description', 'Purchase')
        plan_id = request.data.get('plan_id')
        order_id = request.data.get('order_id')

        metadata = {}
        calculated_amount = None

        if plan_id:
            try:
                plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
            except SubscriptionPlan.DoesNotExist:
                return Response({'error': 'Selected plan is unavailable.'}, status=400)
            calculated_amount = Decimal(plan.price_monthly)
            description = description or f"Subscription to {plan.name}"
            metadata.update({'plan_id': plan_id, 'plan_name': plan.name, 'kind': 'subscription'})

        if order_id:
            from marketplace.models import Order
            try:
                order = Order.objects.get(id=order_id, customer=request.user)
            except Order.DoesNotExist:
                return Response({'error': 'Order not found for this user.'}, status=404)
            calculated_amount = Decimal(order.total_amount)
            description = description or f"Marketplace order #{order.id}"
            metadata.update({'order_id': order.id, 'kind': 'order'})

        if calculated_amount is None:
            if amount is None:
                return Response({'error': 'Either amount, plan_id, or order_id is required.'}, status=400)
            calculated_amount = Decimal(str(amount))
            metadata.update({'kind': 'manual'})
        
        if calculated_amount <= 0:
            return Response({'error': 'Amount must be greater than zero.'}, status=400)

        # Create a pending transaction
        ref_id = f"SSL-{uuid.uuid4().hex[:8].upper()}"
        txn = Transaction.objects.create(
            user=request.user,
            type='debit',
            status='pending',
            amount=calculated_amount,
            description=description,
            reference_id=ref_id,
            metadata=metadata,
            order_id=metadata.get('order_id'),
        )

        # In a real integration, we would POST to SSLCommerz Sandbox to get a URL.
        # Here we mock the behavior for demonstration purposes.
        mock_success_url = f"http://localhost:5173/payment/success?reference={ref_id}&status=success"
        mock_fail_url = f"http://localhost:5173/payment/success?reference={ref_id}&status=failed"
        mock_cancel_url = f"http://localhost:5173/payment/success?reference={ref_id}&status=cancelled"
        
        return Response({
            'transaction_id': txn.id,
            'reference_id': ref_id,
            'payment_url': mock_success_url,
            'payment_url_success': mock_success_url,
            'payment_url_fail': mock_fail_url,
            'payment_url_cancel': mock_cancel_url,
            'amount': str(calculated_amount),
        })


class PaymentCallbackView(APIView):
    """POST /api/finance/payment/callback/ — SSLCommerz IPN simulation."""
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(tags=['Finance'])
    def post(self, request):
        ref_id = request.data.get('reference_id')
        gateway_status = (request.data.get('status') or 'success').lower()
        if not ref_id:
            return Response({'error': 'reference_id is required'}, status=400)

        try:
            txn = Transaction.objects.get(reference_id=ref_id)
            if txn.status == 'pending':
                if gateway_status in ['failed', 'fail', 'error']:
                    txn.status = 'failed'
                    txn.metadata = {**txn.metadata, 'gateway_status': gateway_status}
                    txn.save(update_fields=['status', 'metadata'])
                    return Response({'status': 'Transaction marked failed'})

                if gateway_status in ['cancelled', 'canceled']:
                    txn.status = 'failed'
                    txn.metadata = {**txn.metadata, 'gateway_status': gateway_status}
                    txn.save(update_fields=['status', 'metadata'])
                    return Response({'status': 'Transaction cancelled'})

                txn.status = 'completed'
                txn.metadata = {**txn.metadata, 'gateway_status': 'success'}
                txn.save(update_fields=['status', 'metadata'])
                
                # Check if this was a subscription purchase
                if 'plan_id' in txn.metadata:
                    try:
                        plan = SubscriptionPlan.objects.get(id=txn.metadata['plan_id'])
                        sub, _ = Subscription.objects.get_or_create(
                            user=txn.user,
                            defaults={'plan': plan, 'expires_at': timezone.now() + timedelta(days=30)}
                        )
                        sub.plan = plan
                        sub.status = Subscription.Status.ACTIVE
                        sub.remaining_credits += plan.credits
                        sub.expires_at = max(sub.expires_at, timezone.now()) + timedelta(days=30)
                        sub.save()
                    except SubscriptionPlan.DoesNotExist:
                        pass

                if 'order_id' in txn.metadata:
                    from marketplace.models import Order
                    try:
                        order = Order.objects.get(id=txn.metadata['order_id'])
                        if order.status == Order.Status.PENDING:
                            order.status = Order.Status.PROCESSING
                            order.save(update_fields=['status'])
                    except Order.DoesNotExist:
                        pass
                
                return Response({'status': 'Transaction completed'})
            return Response({'status': f'Transaction already {txn.status}'})
        except Transaction.DoesNotExist:
            return Response({'error': 'Transaction not found'}, status=404)
