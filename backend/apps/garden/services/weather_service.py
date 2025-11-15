"""
Weather Service

OpenWeatherMap API integration for garden weather data.

Provides:
- Current weather conditions
- 5-day forecast
- Weather-based care recommendations
- Caching for cost optimization
"""

import logging
import requests
from typing import Optional, Dict, Any, List
from django.conf import settings
from django.core.cache import cache
from datetime import datetime, timedelta

from ..constants import (
    CACHE_TIMEOUT_WEATHER,
    CACHE_KEY_WEATHER_CURRENT,
    CACHE_KEY_WEATHER_FORECAST,
    FROST_TEMP_F,
    HEATWAVE_TEMP_F,
    HEAVY_RAIN_INCHES
)

logger = logging.getLogger(__name__)


class WeatherService:
    """
    OpenWeatherMap API integration service.

    Free tier: 60 calls/minute, 1000 calls/day
    Caches responses for 1 hour to minimize API usage.
    """

    BASE_URL = 'https://api.openweathermap.org/data/2.5'

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        """Get OpenWeather API key from settings."""
        return getattr(settings, 'OPENWEATHER_API_KEY', None)

    @classmethod
    def get_timeout(cls) -> int:
        """Get API timeout from settings."""
        return getattr(settings, 'OPENWEATHER_API_TIMEOUT', 10)

    @classmethod
    def get_current_weather(
        cls,
        lat: float,
        lng: float
    ) -> Optional[Dict[str, Any]]:
        """
        Get current weather for coordinates.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Weather data dict with:
            - temp (Fahrenheit)
            - conditions (description)
            - humidity (%)
            - wind_speed (mph)
            - precipitation (inches, if raining)
            - sunrise/sunset (timestamps)
        """
        api_key = cls.get_api_key()
        if not api_key:
            logger.warning("[WEATHER] OpenWeather API key not configured")
            return None

        # Check cache first
        cache_key = CACHE_KEY_WEATHER_CURRENT.format(lat=lat, lng=lng)
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"[CACHE] HIT for weather at {lat},{lng}")
            return cached_data

        # Call OpenWeatherMap API
        try:
            url = f'{cls.BASE_URL}/weather'
            params = {
                'lat': lat,
                'lon': lng,
                'appid': api_key,
                'units': 'imperial'  # Fahrenheit, mph
            }

            logger.info(f"[WEATHER] Fetching current weather for {lat},{lng}")
            response = requests.get(url, params=params, timeout=cls.get_timeout())
            response.raise_for_status()

            data = response.json()

            # Parse response
            weather_data = {
                'temp': data['main']['temp'],
                'feels_like': data['main']['feels_like'],
                'conditions': data['weather'][0]['description'],
                'humidity': data['main']['humidity'],
                'wind_speed': data['wind']['speed'],
                'sunrise': data['sys']['sunrise'],
                'sunset': data['sys']['sunset'],
                'timestamp': datetime.now().isoformat()
            }

            # Add precipitation if available
            if 'rain' in data:
                # Rain volume for last 1h (mm) -> convert to inches
                rain_mm = data['rain'].get('1h', 0)
                weather_data['precipitation'] = rain_mm / 25.4
            else:
                weather_data['precipitation'] = 0

            # Cache for 1 hour
            cache.set(cache_key, weather_data, CACHE_TIMEOUT_WEATHER)
            logger.info(f"[WEATHER] Cached current weather for {lat},{lng}")

            return weather_data

        except requests.RequestException as e:
            logger.error(f"[ERROR] OpenWeather API failed: {str(e)}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"[ERROR] Failed to parse weather data: {str(e)}")
            return None

    @classmethod
    def get_forecast(
        cls,
        lat: float,
        lng: float,
        days: int = 5
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get weather forecast for coordinates.

        Args:
            lat: Latitude
            lng: Longitude
            days: Number of days (max 5 for free tier)

        Returns:
            List of daily forecast dicts with:
            - date (YYYY-MM-DD)
            - temp_min (Fahrenheit)
            - temp_max (Fahrenheit)
            - conditions (description)
            - precipitation_probability (%)
            - precipitation_amount (inches)
        """
        api_key = cls.get_api_key()
        if not api_key:
            logger.warning("[WEATHER] OpenWeather API key not configured")
            return None

        # Check cache first
        cache_key = CACHE_KEY_WEATHER_FORECAST.format(lat=lat, lng=lng)
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"[CACHE] HIT for forecast at {lat},{lng}")
            return cached_data

        # Call OpenWeatherMap API
        try:
            url = f'{cls.BASE_URL}/forecast'
            params = {
                'lat': lat,
                'lon': lng,
                'appid': api_key,
                'units': 'imperial'  # Fahrenheit, mph
            }

            logger.info(f"[WEATHER] Fetching forecast for {lat},{lng}")
            response = requests.get(url, params=params, timeout=cls.get_timeout())
            response.raise_for_status()

            data = response.json()

            # Parse forecast (API returns 3-hour intervals)
            # Group by day and aggregate
            daily_forecasts = {}
            for item in data['list']:
                dt = datetime.fromtimestamp(item['dt'])
                date_str = dt.strftime('%Y-%m-%d')

                if date_str not in daily_forecasts:
                    daily_forecasts[date_str] = {
                        'date': date_str,
                        'temp_min': item['main']['temp_min'],
                        'temp_max': item['main']['temp_max'],
                        'conditions': item['weather'][0]['description'],
                        'precipitation_probability': item.get('pop', 0) * 100,
                        'precipitation_amount': 0
                    }
                else:
                    # Update min/max temps
                    daily_forecasts[date_str]['temp_min'] = min(
                        daily_forecasts[date_str]['temp_min'],
                        item['main']['temp_min']
                    )
                    daily_forecasts[date_str]['temp_max'] = max(
                        daily_forecasts[date_str]['temp_max'],
                        item['main']['temp_max']
                    )

                # Add precipitation
                if 'rain' in item:
                    rain_mm = item['rain'].get('3h', 0)
                    daily_forecasts[date_str]['precipitation_amount'] += rain_mm / 25.4

            # Convert to list and limit to requested days
            forecast_list = list(daily_forecasts.values())[:days]

            # Cache for 1 hour
            cache.set(cache_key, forecast_list, CACHE_TIMEOUT_WEATHER)
            logger.info(f"[WEATHER] Cached forecast for {lat},{lng}")

            return forecast_list

        except requests.RequestException as e:
            logger.error(f"[ERROR] OpenWeather API failed: {str(e)}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"[ERROR] Failed to parse forecast data: {str(e)}")
            return None

    @classmethod
    def should_skip_watering(
        cls,
        lat: float,
        lng: float
    ) -> bool:
        """
        Check if watering should be skipped based on weather.

        Returns True if:
        - Heavy rain expected today (>0.5 inches)
        - Recent heavy rain (in current weather)

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            True if watering should be skipped
        """
        # Check current conditions
        current = cls.get_current_weather(lat, lng)
        if current and current.get('precipitation', 0) >= HEAVY_RAIN_INCHES:
            logger.info(f"[WEATHER] Skipping watering due to current rain: {current['precipitation']:.2f} inches")
            return True

        # Check today's forecast
        forecast = cls.get_forecast(lat, lng, days=1)
        if forecast and len(forecast) > 0:
            today = forecast[0]
            if today.get('precipitation_amount', 0) >= HEAVY_RAIN_INCHES:
                logger.info(f"[WEATHER] Skipping watering due to forecast rain: {today['precipitation_amount']:.2f} inches")
                return True

        return False

    @classmethod
    def get_frost_warning(
        cls,
        lat: float,
        lng: float,
        days: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Check for frost warning in next N days.

        Args:
            lat: Latitude
            lng: Longitude
            days: Days to check (default 3)

        Returns:
            Dict with:
            - has_frost: bool
            - frost_date: str (YYYY-MM-DD) if frost expected
            - temp_min: float (minimum temperature)
        """
        forecast = cls.get_forecast(lat, lng, days=days)
        if not forecast:
            return None

        for day in forecast:
            if day['temp_min'] <= FROST_TEMP_F:
                return {
                    'has_frost': True,
                    'frost_date': day['date'],
                    'temp_min': day['temp_min']
                }

        return {
            'has_frost': False,
            'frost_date': None,
            'temp_min': None
        }

    @classmethod
    def get_heatwave_warning(
        cls,
        lat: float,
        lng: float,
        days: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Check for heatwave warning in next N days.

        Args:
            lat: Latitude
            lng: Longitude
            days: Days to check (default 3)

        Returns:
            Dict with:
            - has_heatwave: bool
            - heat_date: str (YYYY-MM-DD) if heatwave expected
            - temp_max: float (maximum temperature)
        """
        forecast = cls.get_forecast(lat, lng, days=days)
        if not forecast:
            return None

        for day in forecast:
            if day['temp_max'] >= HEATWAVE_TEMP_F:
                return {
                    'has_heatwave': True,
                    'heat_date': day['date'],
                    'temp_max': day['temp_max']
                }

        return {
            'has_heatwave': False,
            'heat_date': None,
            'temp_max': None
        }

    @classmethod
    def get_care_recommendations(
        cls,
        lat: float,
        lng: float
    ) -> Dict[str, Any]:
        """
        Get weather-based care recommendations.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Dict with:
            - skip_watering: bool
            - frost_warning: dict or None
            - heat_warning: dict or None
            - recommendations: list of strings
        """
        recommendations = []

        # Check watering
        skip_watering = cls.should_skip_watering(lat, lng)
        if skip_watering:
            recommendations.append("Skip watering due to rain")

        # Check frost
        frost_warning = cls.get_frost_warning(lat, lng)
        if frost_warning and frost_warning['has_frost']:
            recommendations.append(
                f"Frost warning for {frost_warning['frost_date']} "
                f"({frost_warning['temp_min']}°F) - protect sensitive plants"
            )

        # Check heatwave
        heat_warning = cls.get_heatwave_warning(lat, lng)
        if heat_warning and heat_warning['has_heatwave']:
            recommendations.append(
                f"Heat warning for {heat_warning['heat_date']} "
                f"({heat_warning['temp_max']}°F) - water more frequently and provide shade"
            )

        return {
            'skip_watering': skip_watering,
            'frost_warning': frost_warning,
            'heat_warning': heat_warning,
            'recommendations': recommendations
        }
