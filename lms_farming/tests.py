from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from lms_farming.models import LandParcel, CropTrack, CropActivityLog, CropStage, FarmingCycle, CropType
from unittest.mock import patch
import datetime


User = get_user_model()


class LandParcelCRUDTestCase(APITestCase):
    """
    Comprehensive test suite for LandParcel CRUD operations, validation, error handling, and permission constraints.
    """

    def setUp(self):
        # Create users
        self.password = "SecurePassword123"
        
        self.farmer_owner = User.objects.create_user(
            username="owner_farmer",
            email="owner@example.com",
            password=self.password,
            role="farmer"
        )
        
        self.other_farmer = User.objects.create_user(
            username="other_farmer",
            email="other@example.com",
            password=self.password,
            role="farmer"
        )

        # Create dummy land parcel owned by farmer_owner
        self.land = LandParcel.objects.create(
            owner=self.farmer_owner,
            name="Rajshahi Mango Orchard",
            location="Rajshahi North",
            latitude=24.3745000,
            longitude=88.5971000,
            area_acres=2.5,
            soil_type="loamy",
            notes="Well irrigated and fenced"
        )

        from lms_farming.models import CropType
        self.crop_rice = CropType.objects.create(name_en="Rice", name_bn="ধান", is_approved=True)
        self.crop_wheat = CropType.objects.create(name_en="Wheat", name_bn="গম", is_approved=True)

        # Retrieve paths
        self.list_url = reverse('land-list')
        self.detail_url = reverse('land-detail', kwargs={'pk': self.land.id})

    def test_list_land_parcels_paginated(self):
        """Verifies listing land parcels with proper pagination structure."""
        # Authenticate owner
        refresh = RefreshToken.for_user(self.farmer_owner)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        # Add additional land parcels to verify pagination
        for i in range(25):
            LandParcel.objects.create(
                owner=self.farmer_owner,
                name=f"Extra Land {i}",
                location="Rajshahi",
                latitude=24.37,
                longitude=88.59,
                area_acres=1.0,
                soil_type="sandy"
            )

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify DRF pagination metadata fields
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)
        
        # Total lands: 1 (from setUp) + 25 = 26. Default page size in settings is 20.
        self.assertEqual(response.data["count"], 26)
        self.assertEqual(len(response.data["results"]), 20)

        # Verify data structure of results
        first_item = response.data["results"][0]
        self.assertIn("id", first_item)
        self.assertIn("name", first_item)
        self.assertIn("location", first_item)
        self.assertIn("latitude", first_item)
        self.assertIn("longitude", first_item)
        self.assertIn("area_acres", first_item)

    def test_retrieve_single_land_parcel(self):
        """Verifies fetching a single land parcel by ID."""
        refresh = RefreshToken.for_user(self.farmer_owner)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], self.land.name)
        self.assertEqual(float(response.data["area_acres"]), float(self.land.area_acres))

    def test_retrieve_non_existent_land_parcel(self):
        """Verifies retrieving a non-existent land parcel ID returns a 404 error."""
        refresh = RefreshToken.for_user(self.farmer_owner)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        non_existent_url = reverse('land-detail', kwargs={'pk': 99999})
        response = self.client.get(non_existent_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_land_parcel_valid_data(self):
        """Verifies creating a new land parcel with valid data returns 201 Created and saves to DB."""
        refresh = RefreshToken.for_user(self.farmer_owner)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        data = {
            "name": "Bogura Potato Field",
            "location": "Sherpur Bogura",
            "latitude": 24.6784000,
            "longitude": 89.4125000,
            "area_acres": 4.25,
            "soil_type": "clayey",
            "notes": "Rich in organic matter"
        }
        
        initial_count = LandParcel.objects.count()
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(LandParcel.objects.count(), initial_count + 1)
        
        # Verify database entry matches input
        created_land = LandParcel.objects.get(name="Bogura Potato Field")
        self.assertEqual(created_land.owner, self.farmer_owner)
        self.assertEqual(float(created_land.area_acres), 4.25)

    def test_update_land_parcel_full_and_partial(self):
        """Verifies updating a land parcel with full (PUT) and partial (PATCH) requests."""
        refresh = RefreshToken.for_user(self.farmer_owner)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        # 1. Full update (PUT)
        put_data = {
            "name": "Updated Mango Orchard",
            "location": "Rajshahi South",
            "latitude": 24.3746000,
            "longitude": 88.5972000,
            "area_acres": 3.00,
            "soil_type": "sandy loam",
            "notes": "Enlarged area"
        }
        response = self.client.put(self.detail_url, put_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Mango Orchard")
        self.assertEqual(float(response.data["area_acres"]), 3.00)

        # 2. Partial update (PATCH)
        patch_data = {
            "name": "Patched Mango Orchard"
        }
        response = self.client.patch(self.detail_url, patch_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Patched Mango Orchard")
        self.assertEqual(float(response.data["area_acres"]), 3.00) # Unchanged field remains identical

    def test_delete_land_parcel(self):
        """Verifies deleting a land parcel removes it from the database."""
        refresh = RefreshToken.for_user(self.farmer_owner)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        initial_count = LandParcel.objects.count()
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(LandParcel.objects.count(), initial_count - 1)
        
        # Verify it is gone
        self.assertFalse(LandParcel.objects.filter(id=self.land.id).exists())

    def test_create_land_parcel_bad_input(self):
        """Verifies that sending empty fields or invalid data types returns a 400 Bad Request."""
        refresh = RefreshToken.for_user(self.farmer_owner)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        # Blank required field 'name' and invalid datatype for area_acres
        invalid_data = {
            "name": "",
            "location": "Rajshahi",
            "area_acres": "not-a-number"
        }
        response = self.client.post(self.list_url, invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)
        self.assertIn("area_acres", response.data)

    def test_permissions_other_user_restricted(self):
        """Verifies that a user cannot retrieve, update, or delete land owned by another user."""
        # Authenticate other_farmer
        refresh = RefreshToken.for_user(self.other_farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        # Try to GET details (Should return 404 since queryset is restricted to owner's parcels)
        get_response = self.client.get(self.detail_url)
        self.assertEqual(get_response.status_code, status.HTTP_404_NOT_FOUND)

        # Try to PATCH (Should return 404 since queryset is restricted to owner's parcels)
        patch_response = self.client.patch(self.detail_url, {"name": "Hacked name"}, format='json')
        self.assertEqual(patch_response.status_code, status.HTTP_404_NOT_FOUND)

        # Try to DELETE (Should return 404 since queryset is restricted to owner's parcels)
        delete_response = self.client.delete(self.detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Ensure the land parcel is NOT modified or deleted in DB
        self.land.refresh_from_db()
        self.assertEqual(self.land.name, "Rajshahi Mango Orchard")

    def test_crop_track_crud_and_activities(self):
        """Verifies crop track creation, listing, updates, and custom activity log behaviors."""
        refresh = RefreshToken.for_user(self.farmer_owner)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        # 1. Create Crop Track
        list_url = reverse('track-list')
        data = {
            "land": self.land.id,
            "crop": self.crop_rice.id,
            "season": "Winter 2026",
            "status": "active",
            "planted_date": "2026-01-15",
            "expected_harvest_date": "2026-05-15"
        }
        response = self.client.post(list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        track_id = response.data["id"]

        # 2. Get activities list (should be empty initially)
        activities_url = reverse('track-activities', kwargs={'pk': track_id})
        response = self.client.get(activities_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

        # 3. Post irrigation activity
        activity_data = {
            "track": track_id,
            "activity_type": "irrigation",
            "occurred_at": "2026-02-15T08:00:00Z",
            "quantity": 150.00,
            "unit": "liters",
            "notes": "Morning watering"
        }
        response = self.client.post(activities_url, activity_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["activity_type"], "irrigation")

        # 4. Post harvest activity (should trigger autoupdate of track status to 'harvested')
        harvest_data = {
            "track": track_id,
            "activity_type": "harvest",
            "occurred_at": "2026-05-14T12:00:00Z",
            "quantity": 800.00,
            "unit": "kg",
            "notes": "Bumper harvest!"
        }
        response = self.client.post(activities_url, harvest_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        
        # Verify track status changed to harvested
        detail_url = reverse('track-detail', kwargs={'pk': track_id})
        track_response = self.client.get(detail_url)
        self.assertEqual(track_response.data["status"], "harvested")

    def test_crop_stage_crud(self):
        """Verifies creating, listing, and patching crop growth stages."""
        refresh = RefreshToken.for_user(self.farmer_owner)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        # Create base track
        track = CropTrack.objects.create(
            land=self.land,
            crop=self.crop_wheat,
            season="Winter 2026",
            status="active"
        )

        stages_url = reverse('stage-list')
        stage_data = {
            "track": track.id,
            "title": "Flowering Stage",
            "description": "Wheat heads are flowering",
            "started_at": "2026-03-01T00:00:00Z",
            "is_current": True,
            "tasks_json": ["Check moisture", "Apply light fertilizer"]
        }
        response = self.client.post(stages_url, stage_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        stage_id = response.data["id"]

        # Patch stage
        detail_url = reverse('stage-detail', kwargs={'pk': stage_id})
        patch_response = self.client.patch(detail_url, {"is_current": False}, format='json')
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertFalse(patch_response.data["is_current"])

    def test_farming_cycle_crud_and_roi(self):
        """Verifies farming cycles creation and ROI metadata updates."""
        refresh = RefreshToken.for_user(self.farmer_owner)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        cycles_url = reverse('cycle-list')
        cycle_data = {
            "land": self.land.id,
            "name": "Winter Wheat 2026",
            "started_at": "2026-01-01",
            "status": "active",
            "total_investment": 12000.00,
            "expected_yield": 1500.00
        }
        response = self.client.post(cycles_url, cycle_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cycle_id = response.data["id"]

        # Update cycle to completed with revenue
        detail_url = reverse('cycle-detail', kwargs={'pk': cycle_id})
        update_data = {
            "land": self.land.id,
            "name": "Winter Wheat 2026",
            "started_at": "2026-01-01",
            "status": "completed",
            "total_investment": 12000.00,
            "total_revenue": 18000.00,
            "actual_yield": 1600.00
        }
        response = self.client.put(detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "completed")

    @patch('lms_farming.views.get_weather_forecast')
    def test_weather_resolves_via_land_parcel(self, mock_get_weather):
        """Verifies weather forecast coordinates resolve from farmer's land parcel when omitted."""
        # Setup mock weather response
        mock_get_weather.return_value = {
            "current": {"temp": 28.5, "condition": "Sunny"},
            "alerts": []
        }

        # Setup land parcel coordinates
        self.land.latitude = 24.3745000
        self.land.longitude = 88.6042000
        self.land.save()

        refresh = RefreshToken.for_user(self.farmer_owner)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        weather_url = reverse('farming-weather')
        response = self.client.get(weather_url) # Omit coordinates to trigger auto-resolution
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify mock weather was called with parcel's coordinates
        mock_get_weather.assert_called_once_with(lat=24.3745000, lon=88.6042000, days=None)
        self.assertEqual(response.data["current"]["temp"], 28.5)


class CropTypeCRUDTestCase(APITestCase):
    def setUp(self):
        self.password = "SecurePassword123"
        self.admin = User.objects.create_user(
            username="admin_user", email="admin@example.com", password=self.password, role="admin", is_staff=True
        )
        self.farmer = User.objects.create_user(
            username="farmer_user", email="farmer@example.com", password=self.password, role="farmer"
        )
        self.other_farmer = User.objects.create_user(
            username="other_farmer_user", email="other_farmer@example.com", password=self.password, role="farmer"
        )
        self.public_crop = CropType.objects.create(name_en="Public Crop", name_bn="PC", is_approved=True, is_public=True)
        self.suggested_crop = CropType.objects.create(name_en="Suggested", name_bn="SC", suggested_by=self.farmer, is_approved=False, is_public=False)

    def test_list_crops_farmer(self):
        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        response = self.client.get(reverse('crop-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [c['id'] for c in response.data['results']]
        self.assertIn(self.public_crop.id, ids)
        self.assertIn(self.suggested_crop.id, ids)

    def test_list_crops_other_farmer(self):
        refresh = RefreshToken.for_user(self.other_farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        response = self.client.get(reverse('crop-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [c['id'] for c in response.data['results']]
        self.assertIn(self.public_crop.id, ids)
        self.assertNotIn(self.suggested_crop.id, ids)

    def test_list_crops_admin(self):
        refresh = RefreshToken.for_user(self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        response = self.client.get(reverse('crop-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [c['id'] for c in response.data['results']]
        self.assertIn(self.public_crop.id, ids)
        self.assertIn(self.suggested_crop.id, ids)

    def test_farmer_create_crop(self):
        refresh = RefreshToken.for_user(self.farmer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        response = self.client.post(reverse('crop-list'), {"name_en": "New Farmer Crop"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['is_approved'])
        self.assertFalse(response.data['is_public'])

    def test_admin_create_crop(self):
        refresh = RefreshToken.for_user(self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        response = self.client.post(reverse('crop-list'), {"name_en": "New Admin Crop"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_approved'])

    def test_admin_update_crop(self):
        refresh = RefreshToken.for_user(self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        response = self.client.patch(reverse('crop-detail', kwargs={'pk': self.suggested_crop.id}), {"name_en": "Approved Crop"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_approved'])
        self.suggested_crop.refresh_from_db()
        self.assertTrue(self.suggested_crop.is_public)
