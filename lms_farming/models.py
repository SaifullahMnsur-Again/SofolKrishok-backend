from django.db import models
from django.conf import settings


class LandParcel(models.Model):
    """A registered piece of farming land owned by a farmer."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='land_parcels',
    )
    name = models.CharField(max_length=200, help_text="e.g., Rajshahi Mango Garden")
    location = models.CharField(max_length=300, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    area_acres = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    soil_type = models.CharField(max_length=100, blank=True, help_text="Auto-filled by soil classifier")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'land_parcels'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.owner.username})"


class LandParcelHistory(models.Model):
    """Immutable history entries for land parcel changes."""

    class Action(models.TextChoices):
        CREATED = 'created', 'Created'
        UPDATED = 'updated', 'Updated'

    land = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='history_entries')
    action_type = models.CharField(max_length=20, choices=Action.choices)
    summary = models.CharField(max_length=255)
    previous_values = models.JSONField(default=dict, blank=True)
    current_values = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'land_parcel_history'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.land.name}: {self.summary}"


class CropTrack(models.Model):
    """Enrollment of a land parcel into a specific growing season/crop."""

    class Status(models.TextChoices):
        PLANNING = 'planning', 'Planning'
        ACTIVE = 'active', 'Active'
        HARVESTED = 'harvested', 'Harvested'
        COMPLETED = 'completed', 'Completed'

    land = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='crop_tracks')
    crop_name = models.CharField(max_length=100, help_text="e.g., Rice, Wheat, Corn, Potato")
    season = models.CharField(max_length=100, help_text="e.g., Winter 2026, Monsoon 2026")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNING)
    planted_date = models.DateField(null=True, blank=True)
    expected_harvest_date = models.DateField(null=True, blank=True)
    actual_harvest_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'crop_tracks'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.crop_name} on {self.land.name} ({self.season})"


class CropTrackHistory(models.Model):
    """Immutable history entries for farming cycle changes."""

    class Action(models.TextChoices):
        CREATED = 'created', 'Created'
        UPDATED = 'updated', 'Updated'

    track = models.ForeignKey(CropTrack, on_delete=models.CASCADE, related_name='history_entries')
    action_type = models.CharField(max_length=20, choices=Action.choices)
    summary = models.CharField(max_length=255)
    previous_values = models.JSONField(default=dict, blank=True)
    current_values = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'crop_track_history'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.track.crop_name} on {self.track.land.name}: {self.summary}"


class CropStage(models.Model):
    """Individual growth stage within a crop track."""

    track = models.ForeignKey(CropTrack, on_delete=models.CASCADE, related_name='stages')
    title = models.CharField(max_length=200, help_text="e.g., Seedling, Vegetative, Flowering")
    description = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    tasks_json = models.JSONField(default=list, blank=True, help_text="List of tasks for this stage")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'crop_stages'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.title} — {self.track}"
