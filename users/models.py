from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


class CustomUser(AbstractUser):
    """
    Custom user model with role-based access control.
    Roles map to the SofolKrishok portal system.
    """

    class Role(models.TextChoices):
        FARMER = 'farmer', 'Farmer'
        SALES_TEAM_LEAD = 'sales_team_lead', 'Sales Team Lead'
        SERVICE_TEAM_LEAD = 'service_team_lead', 'Service Team Lead'
        SALES_TEAM_MEMBER = 'sales_team_member', 'Sales Team Member'
        SERVICE_TEAM_MEMBER = 'service_team_member', 'Service Team Member'
        SALES = 'sales', 'Sales Team'
        SERVICE = 'service', 'Service Team'
        EXPERT = 'expert', 'Expert'
        BRANCH_MANAGER = 'branch_manager', 'Branch Manager'
        GENERAL_MANAGER = 'general_manager', 'General Manager'
        SITE_ENGINEER = 'site_engineer', 'Site Engineer'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.FARMER,
    )
    zone = models.CharField(max_length=100, blank=True, help_text="Agricultural service zone (e.g. Rajshahi-North)")
    expert_tags = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated expert skills/tags (used for expert allocation and discovery).",
    )
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    preferred_language = models.CharField(
        max_length=5,
        choices=[('bn', 'Bengali'), ('en', 'English')],
        default='bn',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class AuditLog(models.Model):
    """A log of high-value administrative/staff actions."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='audit_actions')
    action_type = models.CharField(max_length=50)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']

class Notification(models.Model):
    """Real-time user notifications for weather, tasks, and system events."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, default='system')
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-timestamp']
