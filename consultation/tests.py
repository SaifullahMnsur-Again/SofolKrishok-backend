from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from consultation.models import ConsultationSlot, Ticket
from users.models import Notification
import datetime

User = get_user_model()


class ConsultationTestCase(APITestCase):
    """
    Test suite for expert slots and ticketing lifecycle, including coverage analytics
    and booking notifications.
    """

    def setUp(self):
        self.password = "SecurePassword123"
        self.farmer = User.objects.create_user(
            username="patient_farmer",
            email="patient@example.com",
            password=self.password,
            role="farmer"
        )
        self.expert = User.objects.create_user(
            username="agri_expert",
            email="expert@example.com",
            password=self.password,
            role="expert"
        )
        self.manager = User.objects.create_user(
            username="consultation_mgr",
            email="mgr@example.com",
            password=self.password,
            role="general_manager"
        )

    def test_consultation_slot_generation(self):
        """Verifies creating individual expert slots and bulk shift-sync generation."""
        # Management / Assigner roles can create shifts
        refresh = RefreshToken.for_user(self.manager)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        url = reverse('slot-list')
        
        # 1. Single slot mode (provide start_time and end_time)
        single_data = {
            "expert": self.expert.id,
            "date": "2026-06-15",
            "start_time": "09:00:00",
            "end_time": "09:20:00",
            "shift": "morning"
        }
        response = self.client.post(url, single_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ConsultationSlot.objects.count(), 1)

        # 2. Shift-sync mode (omit start_time, auto-generates 20-min slots for shift window)
        bulk_data = {
            "expert": self.expert.id,
            "date": "2026-06-16",
            "shift": "afternoon"
        }
        response = self.client.post(url, bulk_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["created"] > 0) # Auto-generated slots
        self.assertTrue(ConsultationSlot.objects.filter(date="2026-06-16", shift="afternoon").exists())

    def test_consultation_coverage_analytics(self):
        """Verifies retrieving shift coverage report analytics."""
        # Create a few slots
        ConsultationSlot.objects.create(
            expert=self.expert,
            date=datetime.date.today(),
            start_time="10:00:00",
            end_time="10:20:00",
            shift="morning",
            is_available=True
        )

        refresh = RefreshToken.for_user(self.manager)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        coverage_url = reverse('slot-coverage')
        response = self.client.get(coverage_url, {"days": 7})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("coverage", response.data)
        self.assertEqual(response.data["days"], 7)

    def test_ticket_booking_and_notifications(self):
        """Verifies booking a slot updates availability and generates notifications for both farmer and expert."""
        slot = ConsultationSlot.objects.create(
            expert=self.expert,
            date="2026-06-15",
            start_time="11:00:00",
            end_time="11:20:00",
            shift="morning",
            is_available=True
        )

        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        book_url = reverse('ticket-book')
        data = {
            "slot_id": slot.id,
            "notes": "Need advice on pest control"
        }
        
        # Verify initial notification counts
        farmer_init_notif = Notification.objects.filter(user=self.farmer).count()
        expert_init_notif = Notification.objects.filter(user=self.expert).count()

        response = self.client.post(book_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify slot availability is updated to False
        slot.refresh_from_db()
        self.assertFalse(slot.is_available)

        # Verify Notifications were generated
        self.assertEqual(Notification.objects.filter(user=self.farmer).count(), farmer_init_notif + 1)
        self.assertEqual(Notification.objects.filter(user=self.expert).count(), expert_init_notif + 1)

    def test_consultation_session_flow(self):
        """Verifies active session start by expert and completion by farmer/expert."""
        slot = ConsultationSlot.objects.create(
            expert=self.expert,
            date="2026-06-15",
            start_time="11:00:00",
            end_time="11:20:00",
            shift="morning",
            is_available=False
        )
        ticket = Ticket.objects.create(
            farmer=self.farmer,
            slot=slot,
            notes="Session notes"
        )

        # 1. Expert starts session
        expert_refresh = RefreshToken.for_user(self.expert)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {expert_refresh.access_token}')

        start_url = reverse('ticket-start-session', kwargs={"pk": ticket.id})
        response = self.client.post(start_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "in_progress")

        # 2. Expert completes session with summary
        complete_url = reverse('ticket-complete-session', kwargs={"pk": ticket.id})
        complete_data = {"expert_summary": "Recommended pesticide ABC"}
        response = self.client.post(complete_url, complete_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["expert_summary"], "Recommended pesticide ABC")
