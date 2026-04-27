from django.db import models
from django.conf import settings


class ConsultationSlot(models.Model):
    """Available 20-minute consultation slots for experts."""

    class Shift(models.TextChoices):
        MORNING = 'morning', 'Morning Shift'
        AFTERNOON = 'afternoon', 'Afternoon Shift'

    expert = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consultation_slots',
        limit_choices_to={'role': 'expert'},
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    shift = models.CharField(max_length=20, choices=Shift.choices)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'consultation_slots'
        ordering = ['date', 'start_time']
        unique_together = ['expert', 'date', 'start_time']

    def __str__(self):
        return f"{self.expert.username} — {self.date} {self.start_time}"


class Ticket(models.Model):
    """Consultation booking ticket."""

    class Status(models.TextChoices):
        BOOKED = 'booked', 'Booked'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        READ_ONLY = 'read_only', 'Read Only (Grace Period)'
        CLOSED = 'closed', 'Closed'
        CANCELLED = 'cancelled', 'Cancelled'

    farmer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consultation_tickets',
    )
    slot = models.OneToOneField(ConsultationSlot, on_delete=models.CASCADE, related_name='ticket')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.BOOKED)
    notes = models.TextField(blank=True, help_text="Farmer's issue description")
    expert_summary = models.TextField(blank=True, help_text="Expert's post-session summary")
    grace_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tickets'
        ordering = ['-created_at']

    def __str__(self):
        return f"Ticket #{self.id} — {self.farmer.username} with {self.slot.expert.username}"
