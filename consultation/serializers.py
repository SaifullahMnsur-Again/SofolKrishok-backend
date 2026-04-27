from rest_framework import serializers
from datetime import time, timedelta, datetime
from .models import ConsultationSlot, Ticket


SHIFT_TIME_WINDOWS = {
    ConsultationSlot.Shift.MORNING: (time(6, 0), time(14, 0)),
    ConsultationSlot.Shift.AFTERNOON: (time(15, 0), time(23, 0)),
}

SLOT_DURATION_MINUTES = 20


def _time_to_minutes(value):
    return value.hour * 60 + value.minute


def _derive_shift(start_time):
    if time(6, 0) <= start_time < time(14, 0):
        return ConsultationSlot.Shift.MORNING
    if time(15, 0) <= start_time < time(23, 0):
        return ConsultationSlot.Shift.AFTERNOON
    return None


class ConsultationSlotSerializer(serializers.ModelSerializer):
    expert_name = serializers.CharField(source='expert.get_full_name', read_only=True)

    def validate(self, attrs):
        shift = attrs.get('shift') or getattr(self.instance, 'shift', None)
        start_time = attrs.get('start_time') or getattr(self.instance, 'start_time', None)

        if start_time is None:
            raise serializers.ValidationError({'start_time': 'Start time is required for a 20-minute consultation slot.'})

        if start_time.second or start_time.microsecond or start_time.minute % SLOT_DURATION_MINUTES != 0:
            raise serializers.ValidationError({'start_time': 'Slots must begin on 20-minute marks (:00, :20, :40).'})

        derived_shift = _derive_shift(start_time)
        if not shift:
            if not derived_shift:
                raise serializers.ValidationError({'shift': 'Start time must fall inside the morning or afternoon shift window.'})
            attrs['shift'] = derived_shift
            shift = derived_shift

        if shift not in SHIFT_TIME_WINDOWS:
            raise serializers.ValidationError({'shift': 'Invalid shift selected.'})

        window_start, window_end = SHIFT_TIME_WINDOWS[shift]
        if not (window_start <= start_time < window_end):
            raise serializers.ValidationError({'start_time': 'Selected start time is outside the chosen shift window.'})

        start_minutes = _time_to_minutes(start_time)
        end_minutes = start_minutes + SLOT_DURATION_MINUTES
        window_end_minutes = _time_to_minutes(window_end)
        if end_minutes > window_end_minutes:
            raise serializers.ValidationError({'start_time': 'Slot must finish before the shift ends.'})

        end_hour, end_minute = divmod(end_minutes, 60)
        attrs['end_time'] = time(end_hour, end_minute)
        return attrs

    class Meta:
        model = ConsultationSlot
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class TicketSerializer(serializers.ModelSerializer):
    slot = ConsultationSlotSerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = '__all__'
        read_only_fields = ['id', 'farmer', 'created_at', 'updated_at']
