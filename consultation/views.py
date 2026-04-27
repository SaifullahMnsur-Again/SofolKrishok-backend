from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import timedelta, time, date as date_cls
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from .models import ConsultationSlot, Ticket
from .serializers import ConsultationSlotSerializer, TicketSerializer, SHIFT_TIME_WINDOWS
from users.models import Notification, CustomUser


@method_decorator(name='list', decorator=swagger_auto_schema(tags=['Consultation']))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(tags=['Consultation']))
@method_decorator(name='create', decorator=swagger_auto_schema(tags=['Consultation']))
@method_decorator(name='update', decorator=swagger_auto_schema(tags=['Consultation']))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(tags=['Consultation']))
@method_decorator(name='destroy', decorator=swagger_auto_schema(tags=['Consultation']))
@method_decorator(name='coverage', decorator=swagger_auto_schema(tags=['Consultation']))
class ConsultationSlotViewSet(viewsets.ModelViewSet):
    serializer_class = ConsultationSlotSerializer
    permission_classes = [permissions.IsAuthenticated]

    ASSIGNER_ROLES = {
        'general_manager',
        'site_engineer',
        'branch_manager',
        'service_team_lead',
        'service_team_member',
        'service',
        'expert',
    }

    def get_queryset(self):
        qs = ConsultationSlot.objects.all()
        if self.request.user.role == 'expert':
            qs = qs.filter(expert=self.request.user)
        date_filter = self.request.query_params.get('date')
        if date_filter:
            try:
                qs = qs.filter(date=date_cls.fromisoformat(date_filter))
            except ValueError:
                qs = qs.none()
        shift_filter = self.request.query_params.get('shift')
        if shift_filter in ConsultationSlot.Shift.values:
            qs = qs.filter(shift=shift_filter)
        expert_id_filter = self.request.query_params.get('expert_id')
        if expert_id_filter:
            try:
                qs = qs.filter(expert_id=int(expert_id_filter))
            except (TypeError, ValueError):
                qs = qs.none()
        available = self.request.query_params.get('available')
        if available == 'true':
            qs = qs.filter(is_available=True)
        return qs

    def check_permissions(self, request):
        super().check_permissions(request)
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            if request.user.role not in self.ASSIGNER_ROLES:
                self.permission_denied(
                    request,
                    message='Only consultation staff can assign expert shifts.',
                )

    def perform_create(self, serializer):
        expert_id = self.request.data.get('expert')
        if not expert_id:
            raise ValidationError({'expert': 'Expert assignment is required for shift scheduling.'})

        try:
            expert = CustomUser.objects.get(id=expert_id, role='expert')
        except CustomUser.DoesNotExist:
            raise ValidationError({'expert': 'Selected user is not a valid expert.'})

        date = serializer.validated_data.get('date')
        shift = serializer.validated_data.get('shift')
        if ConsultationSlot.objects.filter(expert=expert, date=date, shift=shift).exists():
            raise ValidationError({'shift': 'This expert already has that shift assigned for the selected date.'})

        serializer.save(expert=expert)

    def create(self, request, *args, **kwargs):
        start_time_value = request.data.get('start_time')
        if not start_time_value:
            expert_id = request.data.get('expert')
            date_value = request.data.get('date')
            shift_value = request.data.get('shift')

            if not expert_id:
                raise ValidationError({'expert': 'Expert assignment is required for shift scheduling.'})
            if not date_value:
                raise ValidationError({'date': 'Date is required.'})
            if shift_value not in ConsultationSlot.Shift.values:
                raise ValidationError({'shift': 'A valid shift is required.'})

            try:
                expert = CustomUser.objects.get(id=expert_id, role='expert')
            except CustomUser.DoesNotExist:
                raise ValidationError({'expert': 'Selected user is not a valid expert.'})

            window_start, window_end = SHIFT_TIME_WINDOWS[shift_value]
            created = 0
            updated = 0
            slots = []
            parsed_date = date_cls.fromisoformat(date_value)

            current_minutes = window_start.hour * 60 + window_start.minute
            end_minutes = window_end.hour * 60 + window_end.minute

            with transaction.atomic():
                while current_minutes + 20 <= end_minutes:
                    hour, minute = divmod(current_minutes, 60)
                    start_time = time(hour, minute)
                    slot_end_minutes = current_minutes + 20
                    end_hour, end_minute = divmod(slot_end_minutes, 60)
                    end_time = time(end_hour, end_minute)
                    slot, was_created = ConsultationSlot.objects.update_or_create(
                        expert=expert,
                        date=parsed_date,
                        start_time=start_time,
                        defaults={
                            'shift': shift_value,
                            'end_time': end_time,
                            'is_available': True,
                        },
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                    slots.append(slot)
                    current_minutes += 20

            payload = ConsultationSlotSerializer(slots, many=True).data
            return Response(
                {
                    'created': created,
                    'updated': updated,
                    'slots': payload,
                    'message': f'Shift assignments synchronized for {date_value} ({shift_value}).',
                },
                status=status.HTTP_201_CREATED,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
        except IntegrityError:
            raise ValidationError({'shift': 'Duplicate shift allocation for this expert and date.'})
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['get'])
    def coverage(self, request):
        if request.user.role not in self.ASSIGNER_ROLES:
            return Response({'error': 'Only consultation staff can view shift coverage.'}, status=403)

        days = int(request.query_params.get('days', 14))
        days = max(1, min(days, 60))
        expert_id = request.query_params.get('expert_id')
        zone = (request.query_params.get('zone') or '').strip()
        expert_tag = (request.query_params.get('expert_tag') or '').strip()
        start_date = timezone.localdate()
        end_date = start_date + timedelta(days=days - 1)

        slots = ConsultationSlot.objects.filter(date__range=[start_date, end_date]).select_related('expert')
        if expert_id:
            try:
                slots = slots.filter(expert_id=int(expert_id))
            except (TypeError, ValueError):
                return Response({'error': 'expert_id must be a valid integer.'}, status=400)

        if zone:
            slots = slots.filter(expert__zone=zone)

        if expert_tag:
            slots = slots.filter(expert__expert_tags__icontains=expert_tag)

        by_key = {}
        for slot in slots:
            key = (slot.date.isoformat(), slot.shift)
            entry = by_key.get(key)
            if not entry:
                entry = {
                    'date': slot.date.isoformat(),
                    'shift': slot.shift,
                    'total_slots': 0,
                    'booked_slots': 0,
                    'available_slots': 0,
                    'expert_ids': set(),
                }
                by_key[key] = entry

            entry['total_slots'] += 1
            if slot.is_available:
                entry['available_slots'] += 1
            else:
                entry['booked_slots'] += 1
            entry['expert_ids'].add(slot.expert_id)

        coverage = []
        for day_offset in range(days):
            current_date = (start_date + timedelta(days=day_offset)).isoformat()
            for shift in [ConsultationSlot.Shift.MORNING, ConsultationSlot.Shift.AFTERNOON]:
                entry = by_key.get((current_date, shift))
                if not entry:
                    entry = {
                        'date': current_date,
                        'shift': shift,
                        'total_slots': 0,
                        'booked_slots': 0,
                        'available_slots': 0,
                        'expert_ids': set(),
                    }

                total = entry['total_slots']
                load_percent = round((entry['booked_slots'] / total) * 100, 1) if total else 0
                coverage.append({
                    'date': entry['date'],
                    'shift': entry['shift'],
                    'total_slots': total,
                    'booked_slots': entry['booked_slots'],
                    'available_slots': entry['available_slots'],
                    'expert_count': len(entry['expert_ids']),
                    'load_percent': load_percent,
                })

        return Response({
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days,
            'filters': {
                'expert_id': expert_id,
                'zone': zone,
                'expert_tag': expert_tag,
            },
            'coverage': coverage,
        })


@method_decorator(name='list', decorator=swagger_auto_schema(tags=['Consultation']))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(tags=['Consultation']))
@method_decorator(name='create', decorator=swagger_auto_schema(tags=['Consultation']))
@method_decorator(name='update', decorator=swagger_auto_schema(tags=['Consultation']))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(tags=['Consultation']))
@method_decorator(name='destroy', decorator=swagger_auto_schema(tags=['Consultation']))
@method_decorator(name='book', decorator=swagger_auto_schema(tags=['Consultation']))
@method_decorator(name='start_session', decorator=swagger_auto_schema(tags=['Consultation']))
@method_decorator(name='complete_session', decorator=swagger_auto_schema(tags=['Consultation']))
class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'expert':
            return Ticket.objects.filter(slot__expert=user)
        if user.role in ['service_team_lead', 'branch_manager', 'general_manager', 'site_engineer']:
            return Ticket.objects.all()
        return Ticket.objects.filter(farmer=user)

    @action(detail=False, methods=['post'])
    def book(self, request):
        """POST /api/tickets/book/ — Book a consultation slot."""
        slot_id = request.data.get('slot_id')
        notes = request.data.get('notes', '')

        try:
            slot = ConsultationSlot.objects.get(id=slot_id, is_available=True)
        except ConsultationSlot.DoesNotExist:
            return Response(
                {'error': 'Slot not available.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ticket = Ticket.objects.create(
            farmer=request.user,
            slot=slot,
            notes=notes,
        )
        slot.is_available = False
        slot.save(update_fields=['is_available'])

        # Notify Farmer
        Notification.objects.create(
            user=request.user,
            title="Consultation Booked",
            message=f"Session with Dr. {slot.expert.username} confirmed for {slot.date} at {slot.start_time}.",
            notification_type='consultation'
        )
        # Notify Expert
        Notification.objects.create(
            user=slot.expert,
            title="New Patient Booking",
            message=f"Farmer {request.user.username} has booked your {slot.start_time} slot.",
            notification_type='consultation'
        )

        return Response(
            TicketSerializer(ticket).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def start_session(self, request, pk=None):
        """POST /api/tickets/{id}/start_session/ — Expert starts the live session."""
        ticket = self.get_object()
        if request.user != ticket.slot.expert:
            return Response({'error': 'Unauthorized'}, status=403)
        
        ticket.status = Ticket.Status.IN_PROGRESS
        ticket.save(update_fields=['status'])

        # Notify Farmer
        Notification.objects.create(
            user=ticket.farmer,
            title="Expert Joined",
            message=f"Dr. {request.user.username} has entered the room. Start your consultation.",
            notification_type='consultation'
        )

        return Response(TicketSerializer(ticket).data)

    @action(detail=True, methods=['post'])
    def complete_session(self, request, pk=None):
        """POST /api/tickets/{id}/complete_session/ — Farmer or expert closes the room and finalizes summary."""
        ticket = self.get_object()
        if request.user not in {ticket.slot.expert, ticket.farmer}:
            return Response({'error': 'Unauthorized'}, status=403)
        
        summary = request.data.get('expert_summary', '')
        if request.user == ticket.slot.expert:
            ticket.expert_summary = summary
        ticket.status = Ticket.Status.COMPLETED
        if request.user == ticket.slot.expert:
            ticket.save(update_fields=['status', 'expert_summary'])
        else:
            ticket.save(update_fields=['status'])
        return Response(TicketSerializer(ticket).data)
