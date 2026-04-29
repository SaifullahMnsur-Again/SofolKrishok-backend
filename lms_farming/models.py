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


class CropActivityLog(models.Model):
    """Detailed activity memory for a crop track."""

    class ActivityType(models.TextChoices):
        IRRIGATION = 'irrigation', 'Irrigation'
        FERTILIZATION = 'fertilization', 'Fertilization'
        PESTICIDE = 'pesticide', 'Pesticide'
        HARVEST = 'harvest', 'Harvest'
        OTHER = 'other', 'Other'

    track = models.ForeignKey(CropTrack, on_delete=models.CASCADE, related_name='activity_logs')
    activity_type = models.CharField(max_length=20, choices=ActivityType.choices)
    occurred_at = models.DateTimeField()
    quantity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True, help_text='e.g. liters, kg, grams, bags')
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_crop_activities',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'crop_activity_logs'
        ordering = ['-occurred_at', '-created_at']

    def __str__(self):
        return f"{self.track.crop_name}: {self.get_activity_type_display()} @ {self.occurred_at:%Y-%m-%d %H:%M}"


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


class FarmingCycle(models.Model):
    """A farming cycle represents a season/period of farming on a land parcel."""

    class Status(models.TextChoices):
        PLANNING = 'planning', 'Planning'
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        ARCHIVED = 'archived', 'Archived'

    land = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='farming_cycles')
    name = models.CharField(max_length=200, help_text="e.g., Monsoon 2026, Winter 2026")
    description = models.TextField(blank=True)
    started_at = models.DateField()
    expected_end_at = models.DateField(null=True, blank=True)
    actual_end_at = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNING)
    soil_preparation_notes = models.TextField(blank=True)
    expected_yield = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Expected yield in kg")
    actual_yield = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Actual yield in kg")
    total_investment = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Total investment in BDT")
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Total revenue in BDT")
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'farming_cycles'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.name} on {self.land.name}"


class FarmingCycleHistory(models.Model):
    """Immutable history entries for farming cycle modifications."""

    class Action(models.TextChoices):
        CREATED = 'created', 'Created'
        UPDATED = 'updated', 'Updated'
        STATUS_CHANGED = 'status_changed', 'Status Changed'
        COMPLETED = 'completed', 'Completed'

    cycle = models.ForeignKey(FarmingCycle, on_delete=models.CASCADE, related_name='history_entries')
    action_type = models.CharField(max_length=20, choices=Action.choices)
    summary = models.CharField(max_length=255)
    previous_values = models.JSONField(default=dict, blank=True)
    current_values = models.JSONField(default=dict, blank=True)
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='farming_cycle_history_entries',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'farming_cycle_history'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['cycle', '-created_at']),
        ]

    def __str__(self):
        return f"{self.cycle.name}: {self.summary}"
