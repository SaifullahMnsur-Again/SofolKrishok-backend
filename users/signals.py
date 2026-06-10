from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from users.models import Notification

User = get_user_model()

@receiver(post_save, sender=User)
def create_welcome_notification(sender, instance, created, **kwargs):
    if created:
        Notification.objects.create(
            user=instance,
            title="Welcome to SofolKrishok!",
            message=f"Hello {instance.username}, thank you for registering as a {instance.get_role_display()}!",
            notification_type="system_alert"
        )
