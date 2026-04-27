from datetime import datetime

import requests
from django.conf import settings


def _icon_to_emoji(icon: str) -> str:
    mapping = {
        '01d': '☀️', '01n': '🌙',
        '02d': '🌤️', '02n': '☁️',
        '03d': '☁️', '03n': '☁️',
        '04d': '☁️', '04n': '☁️',
        '09d': '🌧️', '09n': '🌧️',
        '10d': '🌦️', '10n': '🌧️',
        '11d': '⛈️', '11n': '⛈️',
        '13d': '❄️', '13n': '❄️',
        '50d': '🌫️', '50n': '🌫️',
    }
    return mapping.get(icon, '🌡️')


def _build_alert(day_forecast: dict):
    alerts = []
    if day_forecast['rain_mm'] >= 20:
        alerts.append('Heavy rain expected')
    if day_forecast['temp_max'] >= 36:
        alerts.append('High heat stress risk')
    if day_forecast['wind_speed'] >= 10:
        alerts.append('Strong wind warning')
    return alerts


def get_weather_forecast(lat: float, lon: float, days: int | None = None) -> dict:
    api_key = settings.OPENWEATHER_API_KEY
    if not api_key:
        raise ValueError('OPENWEATHER_API_KEY is not configured.')

    days = days or getattr(settings, 'WEATHER_FORECAST_DAYS', 5)

    current = requests.get(
        'https://api.openweathermap.org/data/2.5/weather',
        params={'lat': lat, 'lon': lon, 'appid': api_key, 'units': 'metric'},
        timeout=10,
    )
    current.raise_for_status()
    current_data = current.json()

    forecast = requests.get(
        'https://api.openweathermap.org/data/2.5/forecast',
        params={'lat': lat, 'lon': lon, 'appid': api_key, 'units': 'metric'},
        timeout=10,
    )
    forecast.raise_for_status()
    forecast_data = forecast.json()

    grouped = {}
    for item in forecast_data.get('list', []):
        dt = datetime.fromtimestamp(item['dt'])
        day_key = dt.strftime('%Y-%m-%d')
        grouped.setdefault(day_key, []).append(item)

    daily = []
    for day_key, buckets in list(grouped.items())[:days]:
        temps = [b['main']['temp'] for b in buckets]
        wind = [b['wind'].get('speed', 0) for b in buckets]
        rain = [b.get('rain', {}).get('3h', 0) for b in buckets]
        weather = buckets[len(buckets) // 2]['weather'][0]

        day_forecast = {
            'date': day_key,
            'condition': weather.get('main', 'Unknown'),
            'description': weather.get('description', ''),
            'icon': weather.get('icon', ''),
            'emoji': _icon_to_emoji(weather.get('icon', '')),
            'temp_min': round(min(temps), 1),
            'temp_max': round(max(temps), 1),
            'wind_speed': round(max(wind), 1),
            'rain_mm': round(sum(rain), 1),
        }
        day_forecast['alerts'] = _build_alert(day_forecast)
        daily.append(day_forecast)

    current_weather = current_data.get('weather', [{}])[0]

    return {
        'location': current_data.get('name', 'Unknown location'),
        'current': {
            'temp': round(current_data.get('main', {}).get('temp', 0), 1),
            'feels_like': round(current_data.get('main', {}).get('feels_like', 0), 1),
            'humidity': current_data.get('main', {}).get('humidity'),
            'condition': current_weather.get('main', 'Unknown'),
            'description': current_weather.get('description', ''),
            'emoji': _icon_to_emoji(current_weather.get('icon', '')),
        },
        'forecast': daily,
        'alerts': [
            {'date': item['date'], 'message': alert}
            for item in daily
            for alert in item['alerts']
        ],
    }
