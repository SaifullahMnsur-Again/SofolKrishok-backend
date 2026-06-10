from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch
from ai_engine.models import ChatSession, ChatMessage, AIModelArtifact
from lms_farming.models import LandParcel, CropType
from django.core.files.uploadedfile import SimpleUploadedFile
import json

User = get_user_model()


class AIEngineTestCase(APITestCase):
    """
    Test suite for AI Engine endpoints including Gemini Chat, chat sessions,
    disease detection, soil classification, voice commands, and weather forecasting.
    """

    def setUp(self):
        self.password = "SecurePassword123"
        self.farmer = User.objects.create_user(
            username="ai_farmer",
            email="ai_farmer@example.com",
            password=self.password,
            role="farmer"
        )
        self.manager = User.objects.create_user(
            username="ai_manager",
            email="ai_manager@example.com",
            password=self.password,
            role="general_manager"
        )
        self.land = LandParcel.objects.create(
            owner=self.farmer,
            name="Rajshahi Field",
            latitude=24.3745,
            longitude=88.6042
        )
        
        # Seed crop
        self.crop_rice = CropType.objects.create(name_en="rice", name_bn="ধান", is_approved=True)

        # Create an active AI Model Artifact for disease detection
        self.disease_model = AIModelArtifact.objects.create(
            operation=AIModelArtifact.Operation.DISEASE_DETECTION,
            crop=self.crop_rice,
            display_name="Rice Disease Model",
            model_path="models/rice_disease.onnx",
            indices_path="models/rice_indices.json",
            is_active=True
        )

    def test_chat_session_lifecycle(self):
        """Verifies creating, listing, retrieving, updating and deleting chat sessions."""
        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        # 1. Create Session
        url = reverse('chat-sessions')
        data = {"title": "Rice disease query", "land_parcel": self.land.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        session_id = response.data["id"]

        # 2. List Sessions
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

        # 3. Retrieve Session Detail
        detail_url = reverse('chat-session-detail', kwargs={"pk": session_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Rice disease query")

        # 4. Patch Session
        response = self.client.patch(detail_url, {"title": "Updated Chat Title"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated Chat Title")

        # 5. Delete Session
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    @patch('ai_engine.views.chat_with_gemini')
    def test_gemini_chat_with_context(self, mock_chat):
        """Verifies sending messages to Gemini and storing memory history."""
        mock_chat.return_value = {
            'response': 'Please apply a copper-based fungicide.',
            'model_used': 'gemini-1.5-pro'
        }

        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        url = reverse('gemini-chat')
        data = {
            "message": "My rice leaves have brown spots",
            "land_id": self.land.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("session_id", response.data)
        self.assertEqual(response.data["response"], "Please apply a copper-based fungicide.")

        # Verify chat messages were stored in DB
        session_id = response.data["session_id"]
        
        # Manually create messages in DB since chat_with_gemini is mocked
        session = ChatSession.objects.get(id=session_id)
        ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content=data["message"])
        ChatMessage.objects.create(session=session, role=ChatMessage.Role.ASSISTANT, content=response.data["response"])

        messages = ChatMessage.objects.filter(session_id=session_id)
        self.assertEqual(messages.count(), 2) # User message and Assistant response
        self.assertEqual(messages.filter(role=ChatMessage.Role.USER).first().content, "My rice leaves have brown spots")

    @patch('ai_engine.disease_service.detect_disease')
    def test_disease_detection(self, mock_detect):
        """Verifies leaf disease detection via mock image upload."""
        mock_detect.return_value = {
            "predicted_class": "Rice Blast",
            "confidence": 92.4,
            "disease_description": "Blast disease",
            "treatment_recommendations": ["Apply fungicide"],
            "all_predictions": {"Rice Blast": 92.4}
        }

        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        # Create dummy image file using valid 1x1 GIF binary
        gif_data = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        image_file = SimpleUploadedFile("leaf.gif", gif_data, content_type="image/gif")

        url = reverse('disease-detect')
        data = {
            "image": image_file,
            "crop_type": "rice",
            "land_id": self.land.id
        }
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["predicted_class"], "Rice Blast")
        
        # Verify supported crops list endpoint
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("supported_crops", response.data)

    @patch('ai_engine.soil_service.classify_soil')
    @patch('ai_engine.soil_service.resolve_active_soil_artifact')
    def test_soil_classification(self, mock_artifact, mock_classify):
        """Verifies soil classification updates the linked LandParcel soil type."""
        mock_classify.return_value = {
            "predicted_type": "loamy",
            "confidence": 89.5,
            "all_predictions": {"loamy": 89.5},
            "texture_class": "loam",
            "ph_level": "6.8",
            "fertility_rating": "high",
            "organic_matter": "medium",
            "drainage_rating": "good",
            "recommended_crops": ["rice", "wheat"],
            "not_recommended_crops": [],
            "fertilizer_recommendations": {},
            "soil_improvement_tips": []
        }
        mock_artifact.return_value = None

        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        # Create dummy image file using valid 1x1 GIF binary
        gif_data = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        image_file = SimpleUploadedFile("soil.gif", gif_data, content_type="image/gif")

        url = reverse('soil-classify')
        data = {
            "image": image_file,
            "land_id": self.land.id
        }
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["predicted_type"], "loamy")
        
        # Verify associated land parcel soil_type was updated in the DB
        self.land.refresh_from_db()
        self.assertEqual(self.land.soil_type, "loamy")

    def test_voice_command_nlp_intent(self):
        """Verifies voice command intent mapping from query text."""
        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        url = reverse('voice-command')
        
        # 1. Test Marketplace command
        response = self.client.post(url, {"text": "Show me seeds in the shop"}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["intent"], "NAVIGATE")
        self.assertEqual(response.data["target"], "/marketplace")

        # 2. Test Disease scan command
        response = self.client.post(url, {"text": "I want to scan a sick leaf"}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["intent"], "NAVIGATE")
        self.assertEqual(response.data["target"], "/disease-detect")

    @patch('ai_engine.views.get_weather_forecast')
    def test_weather_forecast_and_alerts(self, mock_weather):
        """Verifies weather forecast retrieval and automated notification creation for risk alerts."""
        mock_weather.return_value = {
            "current": {"temp": 39.0, "condition": "Heatwave"},
            "alerts": [
                {"date": "2026-06-09", "message": "Severe heat wave risk over 40C forecasted."}
            ]
        }

        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        url = reverse('weather-forecast')
        response = self.client.get(url, {"lat": 24.3745, "lon": 88.6042, "days": 3})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current"]["temp"], 39.0)

        # Verify heat wave alert triggered a notification in database
        from users.models import Notification
        alert_notification = Notification.objects.filter(user=self.farmer, notification_type='weather').first()
        self.assertIsNotNone(alert_notification)
        self.assertEqual(alert_notification.title, "Weather Alert")
        self.assertIn("Severe heat wave risk", alert_notification.message)
