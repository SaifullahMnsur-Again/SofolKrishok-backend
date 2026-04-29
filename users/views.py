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

@method_decorator(name='post', decorator=swagger_auto_schema(
    tags=['Auth'],
    operation_description='Register a new farmer or staff account.\n\nRoles: farmer, sales, service, expert, sales_team_lead, sales_team_member, service_team_lead, service_team_member, site_engineer, branch_manager, general_manager.',
))
class RegisterView(generics.CreateAPIView):
    """Register a new user account.

    Audience: Both
    
    Create a new farmer or staff member account. After registration, use the login endpoint to obtain JWT tokens.
    
    **Supported Roles:** farmer, sales, service, expert, sales_team_lead, sales_team_member, service_team_lead, service_team_member, site_engineer, branch_manager, general_manager
    
    **Languages:** Bengali (bengali), English (english)
    """
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


@method_decorator(name='get', decorator=swagger_auto_schema(
    tags=['Auth'],
    operation_description='Retrieve current authenticated user\'s profile information.'
))
@method_decorator(name='put', decorator=swagger_auto_schema(
    tags=['Auth'],
    operation_description='Replace entire profile (requires all fields)'
))
@method_decorator(name='patch', decorator=swagger_auto_schema(
    tags=['Auth'],
    operation_description='Partial update to profile (update specific fields only)'
))
class ProfileView(generics.RetrieveUpdateAPIView):
    """Get or update current user profile.

    Audience: Both
    
    **GET:** Retrieve authenticated user's full profile including avatar, zone, and language preferences.
    
    **PUT:** Completely replace profile (all fields required).
    
    **PATCH:** Partially update profile (specify only fields to change).
    
    **Authentication:** Required (Bearer token)
    
    **Permissions:** Users can only modify their own profile.
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class AvatarView(APIView):
    """
    Manage user avatar image.

    Audience: Both
    
    **POST:** Upload a new avatar image (replaces existing). Supported formats: JPEG, PNG. Max size: 5MB.
    
    **DELETE:** Remove avatar image (sets to null).
    
    **Authentication:** Required (Bearer token)
    
    **Returns:** Updated user profile with new avatar URL.
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
    """Change user password.

    Audience: Both
    
    Change the authenticated user's password. Requires providing current password and confirming new password.
    
    **Request Body:**
    - current_password (string): User's current password
    - new_password (string): New password (min 6 chars, must differ from current)
    - confirm_password (string): Confirmation of new password
    
    **Authentication:** Required (Bearer token)
    
    **Validations:**
    - Current password must be correct
    - New password must be at least 6 characters
    - New password must match confirmation
    - New password must differ from current password
    """
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


@method_decorator(name='get', decorator=swagger_auto_schema(
    tags=['Auth'],
    operation_description='List all registered users. Accessible only to managers and team leads.'
))
class UserListView(generics.ListAPIView):
    """List all users.

    Audience: Staff
    
    Retrieve paginated list of all registered users with their profile information.
    
    **Permissions:**
    - general_manager
    - site_engineer
    - branch_manager
    - sales_team_lead
    - service_team_lead
    
    **Returns:** Paginated user list with basic profile info, avatar URL, and role.
    """
    from .serializers import UserListSerializer
    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role in MANAGER_ROLES or self.request.user.role in {'sales_team_lead', 'service_team_lead'}:
            return User.objects.all().order_by('-date_joined')
        return User.objects.none()


@method_decorator(name='post', decorator=swagger_auto_schema(
    tags=['Auth'],
    operation_description='Login and obtain JWT tokens.'
))
class AuthTokenObtainPairView(TokenObtainPairView):
    """User login - obtain JWT tokens.

    Audience: Both
    
    Authenticate user with username/email and password. Returns access token (15 min expiry) and refresh token (7 days expiry).
    
    **Request Body:**
    - username (string): Username or email
    - password (string): User password
    
    **Returns:**
    - access (string): JWT access token for API requests
    - refresh (string): JWT refresh token for obtaining new access tokens
    - user (object): User profile details including role, avatar, and preferences
    
    **Store tokens in localStorage and include in Authorization header:** `Authorization: Bearer {access_token}`
    """


@method_decorator(name='post', decorator=swagger_auto_schema(
    tags=['Auth'],
    operation_description='Refresh access token using refresh token.'
))
class AuthTokenRefreshView(TokenRefreshView):
    """Refresh access token.

    Audience: Both
    
    Use refresh token to obtain a new access token when current one expires (15 min).
    
    **Request Body:**
    - refresh (string): Refresh token obtained from login
    
    **Returns:**
    - access (string): New JWT access token (valid for 15 minutes)
    
    **Note:** Refresh tokens expire after 7 days. Re-login if refresh token is expired.
    """

from .models import AuditLog

@method_decorator(name='list', decorator=swagger_auto_schema(
    tags=['Auth - Admin'],
    operation_description='List all users with full details. Managers and team leads only.'
))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(
    tags=['Auth - Admin'],
    operation_description='Retrieve specific user details. Managers and team leads only.'
))
@method_decorator(name='create', decorator=swagger_auto_schema(
    tags=['Auth - Admin'],
    operation_description='Create new user manually. General managers only.'
))
@method_decorator(name='update', decorator=swagger_auto_schema(
    tags=['Auth - Admin'],
    operation_description='Update user completely (PUT). Managers only.'
))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(
    tags=['Auth - Admin'],
    operation_description='Partially update user (PATCH). Managers only.'
))
@method_decorator(name='destroy', decorator=swagger_auto_schema(
    tags=['Auth - Admin'],
    operation_description='Delete user account. General managers only.'
))
@method_decorator(name='activity', decorator=swagger_auto_schema(
    tags=['Auth - Admin'],
    operation_description='View user activity history.'
))
class UserManagementViewSet(viewsets.ModelViewSet):
    """User management and administration.

    Audience: Staff
    
    Full CRUD operations for user accounts. Accessible only to managers and team leads.
    
    **Available Actions:**
    - GET /users/ - List all users
    - GET /users/{id}/ - Get user details
    - POST /users/ - Create new user
    - PUT /users/{id}/ - Replace user (all fields)
    - PATCH /users/{id}/ - Update user (specific fields)
    - DELETE /users/{id}/ - Delete user
    - GET /users/{id}/activity/ - View user activity history
    
    **Permissions:** general_manager, site_engineer, branch_manager, sales_team_lead, service_team_lead
    """
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

@method_decorator(name='list', decorator=swagger_auto_schema(
    tags=['Auth - Admin'],
    operation_description='List all system audit logs. Managers only.'
))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(
    tags=['Auth - Admin'],
    operation_description='Retrieve specific audit log entry. Managers only.'
))
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """System audit logs (read-only).

    Audience: Staff
    
    View all system-wide audit logs tracking user actions like role changes, account creation, deletions, and administrative operations.
    
    **Available Actions:**
    - GET /audit/ - List all audit logs (paginated)
    - GET /audit/{id}/ - Get specific audit log entry
    
    **Permissions:** general_manager, site_engineer, branch_manager
    
    **Log Types:**
    - user_role_changed: User role was modified
    - user_created: New user account created
    - user_deleted: User account deleted
    - admin_action: General administrative action
    
    **Fields:**
    - user: Who performed the action
    - action_type: Type of action logged
    - description: Human-readable description
    - timestamp: When the action occurred
    - metadata: Additional context data
    """
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role in MANAGER_ROLES:
            return AuditLog.objects.all()
        return AuditLog.objects.none()

@method_decorator(name='list', decorator=swagger_auto_schema(
    tags=['Notifications'],
    operation_description='List all notifications for current user.'
))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(
    tags=['Notifications'],
    operation_description='Get specific notification details.'
))
@method_decorator(name='create', decorator=swagger_auto_schema(
    tags=['Notifications'],
    operation_description='Create a new notification (staff only).'
))
@method_decorator(name='destroy', decorator=swagger_auto_schema(
    tags=['Notifications'],
    operation_description='Delete a notification.'
))
@method_decorator(name='mark_read', decorator=swagger_auto_schema(
    tags=['Notifications'],
    operation_description='Mark notification as read.'
))
class NotificationViewSet(viewsets.ModelViewSet):
    """User notifications.

    Audience: Both
    
    Manage personal notifications including system alerts, order updates, consultation bookings, and administrative notices.
    
    **Available Actions:**
    - GET /notifications/ - List user's notifications
    - GET /notifications/{id}/ - Get notification details
    - POST /notifications/ - Create notification (staff)
    - DELETE /notifications/{id}/ - Delete notification
    - POST /notifications/{id}/mark_read/ - Mark as read
    
    **Authentication:** Required (Bearer token)
    
    **Permissions:** Users see only their own notifications. Staff can create notifications for broadcasting.
    
    **Notification Types:**
    - system_alert: System maintenance, updates, features
    - order_update: Marketplace order status changes
    - consultation_alert: Consultation appointment reminders
    - farming_reminder: Seasonal farming suggestions
    - subscription_alert: Billing and subscription updates
    """
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
