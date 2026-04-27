from celery import shared_task
from django.utils import timezone
from users.models import Notification

@shared_task
def auto_close_expired_tickets():
    """
    Cron Job (Every 10 mins): Closes tickets where the 20-min consultation slot has passed.
    """
    now = timezone.now()
    # In a real scenario, we'd query tickets with status 'in_progress' and expired timers
    # For the simulation, we'll mark some as notifying
    return f"Processed ticket automation at {now}"

@shared_task
def fetch_nasa_power_weather():
    """
    Cron Job (Daily): Fetches localized NASA POWER parameters and caches them in Redis.
    """
    # Mock NASA POWER API call
    # url = "https://power.larc.nasa.gov/api/temporal/daily/point..."
    # r = requests.get(url)
    return "NASA POWER Data synchronized for Rajshahi region."

@shared_task
def process_ai_intent_async(voice_text):
    """
    Async Job: Processes speech to intent using Gemini in the background to avoid UI blocking.
    """
    # Logic to call Gemini and update a notification / socket
    return f"Processed intent: {voice_text}"
