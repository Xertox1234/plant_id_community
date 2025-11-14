"""
Weather Service

Integrates with OpenWeatherMap API to provide weather data for garden planning.

This service handles:
- Current weather conditions
- 5-day weather forecast
- Weather alerts and warnings
- Frost date predictions
- Watering recommendations based on rainfall
"""

import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import requests
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

from ..constants import (
    CACHE_KEY_WEATHER_CURRENT,
    CACHE_KEY_WEATHER_FORECAST,
    CACHE_TIMEOUT_WEATHER,
)

logger = logging.getLogger(__name__)


class WeatherService:
    """
    Service for weather data integration.

    Uses OpenWeatherMap API with aggressive caching to minimize API calls.
    All methods are static to avoid state management.
    """

    # OpenWeatherMap API configuration
    API_BASE_URL = "https://api.openweathermap.org/data/2.5"
    API_KEY = os.getenv('OPENWEATHER_API_KEY', '')

    # Weather thresholds for garden care
    FROST_TEMP_F = 32  # 0°C
    HOT_TEMP_F = 85    # 29°C
    HEAVY_RAIN_INCHES = 0.5  # Per day

    @staticmethod
    def get_current_weather(latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """
        Get current weather conditions for a location.

        Args:
            latitude: Location latitude
            longitude: Location longitude

        Returns:
            Dictionary with current weather data, or None if API call fails
        """
        if not WeatherService.API_KEY:
            logger.warning("[WEATHER] OpenWeatherMap API key not configured")
            return None

        # Check cache first
        cache_key = CACHE_KEY_WEATHER_CURRENT.format(
            lat=f"{latitude:.2f}",
            lng=f"{longitude:.2f}"
        )

        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"[CACHE] HIT for current weather at {latitude}, {longitude}")
            return cached_data

        # Make API call
        logger.info(f"[WEATHER] Fetching current weather for {latitude}, {longitude}")

        try:
            response = requests.get(
                f"{WeatherService.API_BASE_URL}/weather",
                params={
                    'lat': latitude,
                    'lon': longitude,
                    'appid': WeatherService.API_KEY,
                    'units': 'imperial'  # Fahrenheit
                },
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            # Parse and format response
            result = WeatherService._parse_current_weather(data)

            # Cache for 30 minutes
            cache.set(cache_key, result, CACHE_TIMEOUT_WEATHER)
            logger.info(f"[CACHE] SET current weather for {latitude}, {longitude}")

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"[WEATHER] API call failed: {e}")
            return None

    @staticmethod
    def get_forecast(latitude: float, longitude: float, days: int = 5) -> Optional[Dict[str, Any]]:
        """
        Get weather forecast for a location.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            days: Number of days (default: 5, max: 5 with free tier)

        Returns:
            Dictionary with forecast data, or None if API call fails
        """
        if not WeatherService.API_KEY:
            logger.warning("[WEATHER] OpenWeatherMap API key not configured")
            return None

        # Check cache first
        cache_key = CACHE_KEY_WEATHER_FORECAST.format(
            lat=f"{latitude:.2f}",
            lng=f"{longitude:.2f}"
        )

        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"[CACHE] HIT for weather forecast at {latitude}, {longitude}")
            return cached_data

        # Make API call
        logger.info(f"[WEATHER] Fetching {days}-day forecast for {latitude}, {longitude}")

        try:
            response = requests.get(
                f"{WeatherService.API_BASE_URL}/forecast",
                params={
                    'lat': latitude,
                    'lon': longitude,
                    'appid': WeatherService.API_KEY,
                    'units': 'imperial',  # Fahrenheit
                    'cnt': days * 8  # 3-hour intervals, 8 per day
                },
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            # Parse and format response
            result = WeatherService._parse_forecast(data, days)

            # Cache for 1 hour
            cache.set(cache_key, result, 3600)
            logger.info(f"[CACHE] SET weather forecast for {latitude}, {longitude}")

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"[WEATHER] API call failed: {e}")
            return None

    @staticmethod
    def _parse_current_weather(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse OpenWeatherMap current weather response.

        Args:
            data: Raw API response

        Returns:
            Formatted weather data
        """
        main = data.get('main', {})
        weather = data.get('weather', [{}])[0]
        wind = data.get('wind', {})
        rain = data.get('rain', {})

        return {
            'temperature': main.get('temp'),
            'feels_like': main.get('feels_like'),
            'temp_min': main.get('temp_min'),
            'temp_max': main.get('temp_max'),
            'humidity': main.get('humidity'),
            'pressure': main.get('pressure'),
            'description': weather.get('description', '').title(),
            'icon': weather.get('icon'),
            'wind_speed': wind.get('speed'),
            'wind_direction': wind.get('deg'),
            'rainfall_1h': rain.get('1h', 0),
            'rainfall_3h': rain.get('3h', 0),
            'timestamp': datetime.fromtimestamp(data.get('dt', 0)),
            'location': {
                'name': data.get('name'),
                'country': data.get('sys', {}).get('country')
            }
        }

    @staticmethod
    def _parse_forecast(data: Dict[str, Any], days: int) -> Dict[str, Any]:
        """
        Parse OpenWeatherMap forecast response.

        Args:
            data: Raw API response
            days: Number of days requested

        Returns:
            Formatted forecast data grouped by day
        """
        forecast_list = data.get('list', [])

        # Group by day
        daily_forecasts = {}

        for item in forecast_list:
            dt = datetime.fromtimestamp(item.get('dt', 0))
            date_key = dt.strftime('%Y-%m-%d')

            if date_key not in daily_forecasts:
                daily_forecasts[date_key] = {
                    'date': date_key,
                    'temp_min': item['main']['temp_min'],
                    'temp_max': item['main']['temp_max'],
                    'humidity': item['main']['humidity'],
                    'rainfall': item.get('rain', {}).get('3h', 0),
                    'description': item['weather'][0]['description'].title(),
                    'icon': item['weather'][0]['icon'],
                    'intervals': []
                }
            else:
                # Update min/max temps
                daily_forecasts[date_key]['temp_min'] = min(
                    daily_forecasts[date_key]['temp_min'],
                    item['main']['temp_min']
                )
                daily_forecasts[date_key]['temp_max'] = max(
                    daily_forecasts[date_key]['temp_max'],
                    item['main']['temp_max']
                )
                # Accumulate rainfall
                daily_forecasts[date_key]['rainfall'] += item.get('rain', {}).get('3h', 0)

            # Add interval data
            daily_forecasts[date_key]['intervals'].append({
                'time': dt.strftime('%H:%M'),
                'temp': item['main']['temp'],
                'description': item['weather'][0]['description'].title(),
                'rainfall': item.get('rain', {}).get('3h', 0)
            })

        # Convert to sorted list
        forecast_days = sorted(daily_forecasts.values(), key=lambda x: x['date'])[:days]

        return {
            'location': {
                'name': data.get('city', {}).get('name'),
                'country': data.get('city', {}).get('country')
            },
            'days': forecast_days
        }

    @staticmethod
    def get_watering_recommendation(latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Get watering recommendations based on recent and forecasted rainfall.

        Args:
            latitude: Location latitude
            longitude: Location longitude

        Returns:
            Dictionary with watering recommendation
        """
        logger.info(f"[WEATHER] Calculating watering recommendation for {latitude}, {longitude}")

        current = WeatherService.get_current_weather(latitude, longitude)
        forecast = WeatherService.get_forecast(latitude, longitude, days=3)

        if not current or not forecast:
            return {
                'recommendation': 'unable_to_determine',
                'message': 'Weather data unavailable. Use your best judgment.',
                'should_water': None
            }

        # Check recent rainfall
        recent_rainfall = current.get('rainfall_3h', 0)

        # Check forecast rainfall for next 3 days
        forecast_rainfall = sum(
            day.get('rainfall', 0) for day in forecast.get('days', [])
        )

        total_rainfall = recent_rainfall + forecast_rainfall

        # Temperature check
        current_temp = current.get('temperature', 70)
        max_temp_forecast = max(
            (day.get('temp_max', 70) for day in forecast.get('days', [])),
            default=70
        )

        # Watering recommendation logic
        if total_rainfall >= WeatherService.HEAVY_RAIN_INCHES:
            return {
                'recommendation': 'skip_watering',
                'message': f"Sufficient rainfall expected ({total_rainfall:.2f} inches). Skip watering.",
                'should_water': False,
                'rainfall_inches': total_rainfall,
                'current_temp_f': current_temp
            }

        if max_temp_forecast >= WeatherService.HOT_TEMP_F:
            return {
                'recommendation': 'water_recommended',
                'message': f"Hot weather forecast ({max_temp_forecast}°F). Water thoroughly.",
                'should_water': True,
                'rainfall_inches': total_rainfall,
                'current_temp_f': current_temp
            }

        if total_rainfall > 0.1:
            return {
                'recommendation': 'reduce_watering',
                'message': f"Light rainfall expected ({total_rainfall:.2f} inches). Reduce watering frequency.",
                'should_water': False,
                'rainfall_inches': total_rainfall,
                'current_temp_f': current_temp
            }

        return {
            'recommendation': 'normal_watering',
            'message': "No significant rainfall expected. Maintain normal watering schedule.",
            'should_water': True,
            'rainfall_inches': total_rainfall,
            'current_temp_f': current_temp
        }

    @staticmethod
    def check_frost_risk(latitude: float, longitude: float, days_ahead: int = 5) -> Dict[str, Any]:
        """
        Check for frost risk in upcoming forecast.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            days_ahead: Number of days to check (default: 5)

        Returns:
            Dictionary with frost risk assessment
        """
        logger.info(f"[WEATHER] Checking frost risk for {latitude}, {longitude}")

        forecast = WeatherService.get_forecast(latitude, longitude, days=days_ahead)

        if not forecast:
            return {
                'frost_risk': 'unknown',
                'message': 'Weather data unavailable.',
                'frost_dates': []
            }

        frost_dates = []

        for day in forecast.get('days', []):
            if day.get('temp_min', 100) <= WeatherService.FROST_TEMP_F:
                frost_dates.append({
                    'date': day['date'],
                    'temp_min': day['temp_min'],
                    'description': day['description']
                })

        if frost_dates:
            return {
                'frost_risk': 'high',
                'message': f"Frost expected on {len(frost_dates)} day(s). Protect tender plants!",
                'frost_dates': frost_dates,
                'protective_actions': [
                    'Cover tender plants with frost cloth or sheets',
                    'Move potted plants indoors',
                    'Water plants before frost (wet soil retains heat)',
                    'Harvest any frost-sensitive crops'
                ]
            }

        # Check if temperatures are close to freezing
        min_temp = min((day.get('temp_min', 100) for day in forecast.get('days', [])), default=100)
        if min_temp <= 40:
            return {
                'frost_risk': 'moderate',
                'message': f"Low temperatures expected (min: {min_temp}°F). Monitor conditions.",
                'frost_dates': [],
                'protective_actions': [
                    'Be prepared to cover plants if temperatures drop further',
                    'Check weather updates daily'
                ]
            }

        return {
            'frost_risk': 'low',
            'message': "No frost risk in the forecast.",
            'frost_dates': [],
            'protective_actions': []
        }

    @staticmethod
    def invalidate_cache(latitude: float, longitude: float) -> None:
        """
        Invalidate weather cache for a location.

        Args:
            latitude: Location latitude
            longitude: Location longitude
        """
        cache_keys = [
            CACHE_KEY_WEATHER_CURRENT.format(lat=f"{latitude:.2f}", lng=f"{longitude:.2f}"),
            CACHE_KEY_WEATHER_FORECAST.format(lat=f"{latitude:.2f}", lng=f"{longitude:.2f}")
        ]

        for key in cache_keys:
            cache.delete(key)

        logger.info(f"[CACHE] INVALIDATED weather cache for {latitude}, {longitude}")
