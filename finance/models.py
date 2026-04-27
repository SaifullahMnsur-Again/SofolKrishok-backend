from django.db import models
from django.conf import settings


class SubscriptionPlan(models.Model):
    """Available subscription tiers."""

    class PlanType(models.TextChoices):
        PRIMARY = 'primary', 'Primary'
        ADDON = 'addon', 'Add-On'

    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PlanType.choices, default=PlanType.PRIMARY)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    credits = models.PositiveIntegerField(help_text="Number of consultation credits included")
    disease_detection_limit = models.PositiveIntegerField(default=0, help_text="Monthly disease detection scans")
    ai_assistant_daily_limit = models.PositiveIntegerField(default=0, help_text="Daily AI assistant messages")
    expert_appointment_limit = models.PositiveIntegerField(default=0, help_text="Monthly expert appointments")
    market_prediction_limit = models.PositiveIntegerField(default=0, help_text="Monthly market analysis requests")
    farming_suggestion_limit = models.PositiveIntegerField(default=0, help_text="Monthly smart farming suggestions")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    features_json = models.JSONField(default=list, help_text="List of feature strings")
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    offline_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'subscription_plans'
        ordering = ['price_monthly']

    def __str__(self):
        return f"{self.name} — ৳{self.price_monthly}/month"


class Subscription(models.Model):
    """User's active subscription."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        EXPIRED = 'expired', 'Expired'
        CANCELLED = 'cancelled', 'Cancelled'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    remaining_credits = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'subscriptions'

    def __str__(self):
        return f"{self.user.username} — {self.plan.name}"


class Transaction(models.Model):
    """Financial ledger entry."""

    class Type(models.TextChoices):
        CREDIT = 'credit', 'Credit'
        DEBIT = 'debit', 'Debit'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=10, choices=Type.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=500)
    reference_id = models.CharField(max_length=200, blank=True, help_text="SSLCommerz transaction ID")
    order = models.ForeignKey(
        'marketplace.Order',
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_type_display()} ৳{self.amount} — {self.user.username}"
