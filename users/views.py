from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import get_user_model
from .serializers import RegisterSerializer, UserProfileSerializer

User = get_user_model()

MANAGER_ROLES = {'general_manager', 'site_engineer', 'branch_manager'}
STAFF_ROLES = {
    'general_manager', 'site_engineer', 'branch_manager',
    'sales', 'service', 'expert',
    'sales_team_lead', 'service_team_lead',
    'sales_team_member', 'service_team_member',
}

@method_decorator(name='post', decorator=swagger_auto_schema(tags=['Auth']))
class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — Create a new user account."""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                'message': 'Registration successful.',
                'user': UserProfileSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(name='get', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='put', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='patch', decorator=swagger_auto_schema(tags=['Auth']))
class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PUT/PATCH /api/auth/profile/ — View or update current user profile."""
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class AvatarView(APIView):
    """
    POST  /api/auth/avatar/ — Upload or replace avatar image.
    DELETE /api/auth/avatar/ — Remove avatar (set to null).
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(tags=['Auth'])
    def post(self, request):
        file = request.FILES.get('avatar')
        if not file:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        # Delete old avatar file from disk if it exists
        if user.avatar:
            try:
                user.avatar.delete(save=False)
            except Exception:
                pass
        user.avatar = file
        user.save(update_fields=['avatar'])
        serializer = UserProfileSerializer(user, context={'request': request})
        return Response(serializer.data)

    @swagger_auto_schema(tags=['Auth'])
    def delete(self, request):
        user = request.user
        if user.avatar:
            try:
                user.avatar.delete(save=False)
            except Exception:
                pass
            user.avatar = None
            user.save(update_fields=['avatar'])
        serializer = UserProfileSerializer(user, context={'request': request})
        return Response(serializer.data)


class ChangePasswordView(APIView):
    """POST /api/auth/change-password/ — Change the authenticated user's password."""
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(tags=['Auth'])
    def post(self, request):
        current = request.data.get('current_password', '')
        new_pw = request.data.get('new_password', '')
        confirm_pw = request.data.get('confirm_password', '')

        if not request.user.check_password(current):
            return Response({'detail': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(new_pw) < 6:
            return Response({'detail': 'New password must be at least 6 characters.'}, status=status.HTTP_400_BAD_REQUEST)
        if new_pw != confirm_pw:
            return Response({'detail': 'New passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)
        if new_pw == current:
            return Response({'detail': 'New password must differ from current password.'}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(new_pw)
        request.user.save(update_fields=['password'])
        return Response({'detail': 'Password changed successfully.'})


@method_decorator(name='get', decorator=swagger_auto_schema(tags=['Auth']))
class UserListView(generics.ListAPIView):
    """GET /api/auth/users/ — List all users (managers only)."""
    from .serializers import UserListSerializer
    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role in MANAGER_ROLES or self.request.user.role in {'sales_team_lead', 'service_team_lead'}:
            return User.objects.all().order_by('-date_joined')
        return User.objects.none()


@method_decorator(name='post', decorator=swagger_auto_schema(tags=['Auth']))
class AuthTokenObtainPairView(TokenObtainPairView):
    """POST /api/auth/login/ — Issue access and refresh tokens."""


@method_decorator(name='post', decorator=swagger_auto_schema(tags=['Auth']))
class AuthTokenRefreshView(TokenRefreshView):
    """POST /api/auth/token/refresh/ — Refresh access token."""

from .models import AuditLog

@method_decorator(name='list', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='create', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='update', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='destroy', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='activity', decorator=swagger_auto_schema(tags=['Auth']))
class UserManagementViewSet(viewsets.ModelViewSet):
    """CRUD for Users (Managers only)."""
    from .serializers import UserListSerializer
    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role in MANAGER_ROLES:
            return User.objects.all()
        return User.objects.none()

    def perform_update(self, serializer):
        user_before = self.get_object()
        old_role = user_before.role
        updated_user = serializer.save()
        if old_role != updated_user.role:
            AuditLog.objects.create(
                user=self.request.user,
                action_type='ROLE_UPDATE',
                description=f"Updated {updated_user.username} role from {old_role} to {updated_user.role}"
            )

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.user.role not in MANAGER_ROLES:
            self.permission_denied(request, message="Management restricted to Directors.")

    @action(detail=True, methods=['get'])
    def activity(self, request, pk=None):
        """GET /api/auth/manage/{id}/activity/ — Return farmer/staff activity drilldown."""
        target_user = self.get_object()

        if target_user.role == 'farmer':
            from lms_farming.models import LandParcel, CropTrack
            from consultation.models import Ticket
            from marketplace.models import Order
            from finance.models import Transaction

            land_count = LandParcel.objects.filter(owner=target_user).count()
            track_count = CropTrack.objects.filter(land__owner=target_user).count()
            ticket_count = Ticket.objects.filter(farmer=target_user).count()
            order_count = Order.objects.filter(customer=target_user).count()
            txn_count = Transaction.objects.filter(user=target_user).count()

            recent_tickets = Ticket.objects.filter(farmer=target_user).select_related('slot__expert')[:5]
            recent_orders = Order.objects.filter(customer=target_user)[:5]

            return Response({
                'user_type': 'farmer',
                'summary': {
                    'lands': land_count,
                    'crop_tracks': track_count,
                    'consultations': ticket_count,
                    'orders': order_count,
                    'transactions': txn_count,
                },
                'recent_consultations': [
                    {
                        'id': t.id,
                        'status': t.status,
                        'date': str(t.slot.date),
                        'expert': t.slot.expert.username,
                    }
                    for t in recent_tickets
                ],
                'recent_orders': [
                    {
                        'id': o.id,
                        'status': o.status,
                        'amount': str(o.total_amount),
                        'created_at': o.created_at,
                    }
                    for o in recent_orders
                ],
            })

        from consultation.models import ConsultationSlot, Ticket

        audit_logs = AuditLog.objects.filter(user=target_user)[:20]
        slot_count = ConsultationSlot.objects.filter(expert=target_user).count() if target_user.role == 'expert' else 0
        handled_tickets = Ticket.objects.filter(slot__expert=target_user).count() if target_user.role == 'expert' else 0

        return Response({
            'user_type': 'staff',
            'summary': {
                'audit_actions': audit_logs.count(),
                'expert_slots': slot_count,
                'expert_consultations': handled_tickets,
            },
            'recent_activities': [
                {
                    'id': log.id,
                    'action_type': log.action_type,
                    'description': log.description,
                    'timestamp': log.timestamp,
                }
                for log in audit_logs
            ],
        })

from .serializers import AuditLogSerializer, NotificationSerializer

@method_decorator(name='list', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(tags=['Auth']))
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """View only hub for administrative audit logs."""
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role in MANAGER_ROLES:
            return AuditLog.objects.all()
        return AuditLog.objects.none()

@method_decorator(name='list', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='create', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='update', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='destroy', decorator=swagger_auto_schema(tags=['Auth']))
@method_decorator(name='mark_read', decorator=swagger_auto_schema(tags=['Auth']))
class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for user notifications."""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.request.user.notifications.all()

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({'status': 'marked as read'})
