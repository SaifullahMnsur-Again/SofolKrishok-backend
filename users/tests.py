import io
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import Notification

User = get_user_model()


class UserAuthAndSignalsTestCase(APITestCase):
    """
    Test suite for Authentication, Security, Token Operations, Avatar Management, and Signals.
    """

    def setUp(self):
        # Create dummy users for testing auth and permissions
        self.password = "SecurePass123"
        
        # Regular Farmer user
        self.farmer = User.objects.create_user(
            username="farmer1",
            email="farmer1@example.com",
            password=self.password,
            first_name="Farmer",
            last_name="One",
            phone="+8801700000001",
            role="farmer"
        )
        
        # Staff General Manager user
        self.manager = User.objects.create_user(
            username="manager1",
            email="manager1@example.com",
            password=self.password,
            first_name="General",
            last_name="Manager",
            phone="+8801700000002",
            role="general_manager"
        )

        # Retrieve paths
        self.login_url = reverse('token_obtain_pair')
        self.refresh_url = reverse('token_refresh')
        self.logout_url = reverse('logout')
        self.profile_url = reverse('profile')
        self.avatar_url = reverse('avatar')

    def test_jwt_login_valid_credentials(self):
        """Verifies that valid credentials return access and refresh tokens."""
        data = {
            "username": self.farmer.username,
            "password": self.password
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)


    def test_jwt_login_invalid_credentials(self):
        """Verifies that login fails with incorrect credentials."""
        data = {
            "username": self.farmer.username,
            "password": "WrongPassword!"
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_route_protection_unauthorized(self):
        """Verifies that accessing protected paths without authorization returns 401 Unauthorized."""
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh(self):
        """Verifies that access tokens can be refreshed using a valid refresh token."""
        # Authenticate and get tokens
        refresh = RefreshToken.for_user(self.farmer)
        data = {
            "refresh": str(refresh)
        }
        response = self.client.post(self.refresh_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_logout_and_token_invalidation(self):
        """Verifies that logging out invalidates (blacklists) the refresh token."""
        # Get token for farmer
        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Logout call
        logout_data = {
            "refresh": str(refresh)
        }
        response = self.client.post(self.logout_url, logout_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Successfully logged out.")

        # Attempt to refresh token using the blacklisted refresh token - should fail
        refresh_data = {
            "refresh": str(refresh)
        }
        # Reset auth headers to test refresh endpoint (AllowAny)
        self.client.credentials()
        refresh_response = self.client.post(self.refresh_url, refresh_data, format='json')
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_avatar_upload_and_delete(self):
        """Verifies posting a mock image file via SimpleUploadedFile and deleting it."""
        # Authenticate
        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        # Create dummy image in memory
        image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
        avatar_file = SimpleUploadedFile("avatar.png", image_content, content_type="image/png")

        # Upload avatar
        upload_response = self.client.post(self.avatar_url, {"avatar": avatar_file}, format='multipart')
        self.assertEqual(upload_response.status_code, status.HTTP_200_OK)
        self.farmer.refresh_from_db()
        self.assertTrue(self.farmer.avatar.name.startswith("avatars/avatar"))
        self.assertIsNotNone(upload_response.data["avatar_url"])

        # Delete avatar
        delete_response = self.client.delete(self.avatar_url)
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.farmer.refresh_from_db()
        self.assertFalse(self.farmer.avatar)
        self.assertIsNone(delete_response.data["avatar_url"])

    def test_welcome_notification_signal_triggers(self):
        """Verifies that registering a new user triggers the post_save signal creating a welcome notification."""
        # Count notifications before registration
        initial_notification_count = Notification.objects.count()

        # Create user via database helper (which triggers signals)
        new_user = User.objects.create_user(
            username="new_farmer_signal_test",
            email="signal_test@example.com",
            password="SecurePassword123!",
            role="farmer"
        )

        # Assert notification was created
        self.assertEqual(Notification.objects.count(), initial_notification_count + 1)
        notification = Notification.objects.filter(user=new_user).first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.title, "Welcome to SofolKrishok!")
        self.assertEqual(notification.notification_type, "system_alert")
        self.assertIn("new_farmer_signal_test", notification.message)

    def test_change_password(self):
        """Verifies changing user password via change-password view."""
        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        change_password_url = reverse('change-password')
        data = {
            "current_password": self.password,
            "new_password": "NewSecurePassword123!",
            "confirm_password": "NewSecurePassword123!"
        }
        response = self.client.post(change_password_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.farmer.refresh_from_db()
        self.assertTrue(self.farmer.check_password("NewSecurePassword123!"))

    def test_notifications_list_and_mark_read(self):
        """Verifies fetching notifications and marking one as read."""
        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Clear welcome notification from signal so count is exactly 1 after creating the new one
        from users.models import Notification
        Notification.objects.filter(user=self.farmer).delete()
        
        notification = Notification.objects.create(
            user=self.farmer,
            title="Test Alert",
            message="Test message details",
            notification_type="system_alert"
        )
        
        notifications_list_url = reverse('notifications-list')
        response = self.client.get(notifications_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        
        mark_read_url = reverse('notifications-mark-read', kwargs={'pk': notification.id})
        mark_response = self.client.post(mark_read_url)
        self.assertEqual(mark_response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_audit_logs_read(self):
        """Verifies retrieving audit logs requires appropriate permissions."""
        from users.models import AuditLog
        AuditLog.objects.create(
            user=self.farmer,
            action_type="LOGIN",
            description="User logged in"
        )
        
        audit_url = reverse('audit-logs-list')
        
        # 1. Farmer gets no audit logs
        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        response = self.client.get(audit_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)
        
        # 2. General Manager gets audit logs
        gm = User.objects.create_user(
            username="general_manager_test",
            email="gm@example.com",
            password="SecurePassword123!",
            role="general_manager"
        )
        gm_refresh = RefreshToken.for_user(gm)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {gm_refresh.access_token}')
        gm_response = self.client.get(audit_url)
        self.assertEqual(gm_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(gm_response.data["results"]), 1)

    def test_user_management_crud(self):
        """Verifies user accounts CRUD management by general manager and forbidden to farmer."""
        manage_url = reverse('user-manage-list')
        
        # 1. Farmer gets forbidden (403)
        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        response = self.client.get(manage_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # 2. General Manager gets list and can CRUD
        gm = User.objects.create_user(
            username="gm_admin_test",
            email="gm_admin@example.com",
            password="SecurePassword123!",
            role="general_manager"
        )
        gm_refresh = RefreshToken.for_user(gm)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {gm_refresh.access_token}')
        
        gm_response = self.client.get(manage_url)
        self.assertEqual(gm_response.status_code, status.HTTP_200_OK)
        
        # Create a new user account
        create_response = self.client.post(manage_url, {
            "username": "managed_user",
            "email": "managed@example.com",
            "password": "Password123!",
            "role": "sales"
        }, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        new_user_id = create_response.data["id"]
        
        # Update user role
        detail_url = reverse('user-manage-detail', kwargs={'pk': new_user_id})
        update_response = self.client.patch(detail_url, {"role": "expert"}, format='json')
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["role"], "expert")
        
        # Delete user account
        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

