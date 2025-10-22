"""
Monitoring service for plant identification APIs and system performance.

This service tracks API usage, rate limits, cache performance, and provides
alerts when thresholds are approaching.
"""

import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class APIMonitoringService:
    """
    Monitor API usage, rate limits, and system performance.
    """
    
    # Cache keys for different metrics
    CACHE_KEYS = {
        'trefle_calls_hour': 'monitor:trefle:calls_hour',
        'trefle_calls_day': 'monitor:trefle:calls_day',
        'plantnet_calls_hour': 'monitor:plantnet:calls_hour',
        'plantnet_calls_day': 'monitor:plantnet:calls_day',
        'cache_hits': 'monitor:cache:hits',
        'cache_misses': 'monitor:cache:misses',
        'local_db_hits': 'monitor:local:hits',
        'identification_requests': 'monitor:requests:total',
    }
    
    # Rate limits for different APIs
    RATE_LIMITS = {
        'trefle': {'hourly': 120, 'daily': 1000},
        'plantnet': {'hourly': 100, 'daily': 500},
    }
    
    # Alert thresholds (percentage of limit)
    ALERT_THRESHOLDS = {
        'warning': 0.8,   # 80% of limit
        'critical': 0.95  # 95% of limit
    }
    
    def __init__(self):
        """Initialize the monitoring service."""
        self.current_hour = timezone.now().replace(minute=0, second=0, microsecond=0)
    
    def record_api_call(self, api_name: str, endpoint: str = None, success: bool = True):
        """
        Record an API call for monitoring purposes.
        
        Args:
            api_name: Name of the API ('trefle', 'plantnet')
            endpoint: API endpoint called (optional)
            success: Whether the call was successful
        """
        now = timezone.now()
        hour_key = f"{self.CACHE_KEYS[f'{api_name}_calls_hour']}:{now.strftime('%Y%m%d%H')}"
        day_key = f"{self.CACHE_KEYS[f'{api_name}_calls_day']}:{now.strftime('%Y%m%d')}"
        
        # Increment counters
        cache.set(hour_key, cache.get(hour_key, 0) + 1, timeout=3700)  # 1 hour + buffer
        cache.set(day_key, cache.get(day_key, 0) + 1, timeout=86500)   # 1 day + buffer
        
        # Record detailed call info
        call_info = {
            'timestamp': now.isoformat(),
            'api': api_name,
            'endpoint': endpoint,
            'success': success
        }
        
        # Store recent calls for debugging (last 100)
        recent_calls_key = f"monitor:{api_name}:recent"
        recent_calls = cache.get(recent_calls_key, [])
        recent_calls.append(call_info)
        if len(recent_calls) > 100:
            recent_calls = recent_calls[-100:]  # Keep only last 100
        cache.set(recent_calls_key, recent_calls, timeout=3600)
        
        logger.debug(f"Recorded {api_name} API call: {endpoint} ({'success' if success else 'failed'})")
    
    def record_cache_hit(self, cache_type: str = 'redis'):
        """Record a cache hit for performance monitoring."""
        key = f"{self.CACHE_KEYS['cache_hits']}:{cache_type}"
        cache.set(key, cache.get(key, 0) + 1, timeout=3600)
    
    def record_cache_miss(self, cache_type: str = 'redis'):
        """Record a cache miss for performance monitoring."""
        key = f"{self.CACHE_KEYS['cache_misses']}:{cache_type}"
        cache.set(key, cache.get(key, 0) + 1, timeout=3600)
    
    def record_local_db_hit(self):
        """Record when data was served from local database."""
        cache.set(
            self.CACHE_KEYS['local_db_hits'],
            cache.get(self.CACHE_KEYS['local_db_hits'], 0) + 1,
            timeout=3600
        )
    
    def record_identification_request(self, source: str = 'web'):
        """Record an identification request."""
        now = timezone.now()
        day_key = f"{self.CACHE_KEYS['identification_requests']}:{now.strftime('%Y%m%d')}"
        cache.set(day_key, cache.get(day_key, 0) + 1, timeout=86500)
    
    def get_api_usage(self, api_name: str) -> Dict:
        """
        Get current API usage statistics.
        
        Args:
            api_name: Name of the API ('trefle', 'plantnet')
            
        Returns:
            Dictionary with usage statistics
        """
        now = timezone.now()
        hour_key = f"{self.CACHE_KEYS[f'{api_name}_calls_hour']}:{now.strftime('%Y%m%d%H')}"
        day_key = f"{self.CACHE_KEYS[f'{api_name}_calls_day']}:{now.strftime('%Y%m%d')}"
        
        hourly_calls = cache.get(hour_key, 0)
        daily_calls = cache.get(day_key, 0)
        
        limits = self.RATE_LIMITS.get(api_name, {})
        
        usage = {
            'api_name': api_name,
            'hourly_calls': hourly_calls,
            'hourly_limit': limits.get('hourly', 0),
            'hourly_percentage': (hourly_calls / limits.get('hourly', 1)) * 100 if limits.get('hourly') else 0,
            'daily_calls': daily_calls,
            'daily_limit': limits.get('daily', 0),
            'daily_percentage': (daily_calls / limits.get('daily', 1)) * 100 if limits.get('daily') else 0,
            'rate_limited': cache.get(f"{api_name}_rate_limited", False),
            'last_updated': now.isoformat()
        }
        
        # Add alert levels
        usage['hourly_alert_level'] = self._get_alert_level(usage['hourly_percentage'])
        usage['daily_alert_level'] = self._get_alert_level(usage['daily_percentage'])
        
        return usage
    
    def get_cache_performance(self) -> Dict:
        """Get cache performance statistics."""
        hits = cache.get(self.CACHE_KEYS['cache_hits'], 0)
        misses = cache.get(self.CACHE_KEYS['cache_misses'], 0)
        local_hits = cache.get(self.CACHE_KEYS['local_db_hits'], 0)
        
        total_requests = hits + misses + local_hits
        
        return {
            'cache_hits': hits,
            'cache_misses': misses,
            'local_db_hits': local_hits,
            'total_requests': total_requests,
            'cache_hit_ratio': (hits / max(total_requests, 1)) * 100,
            'local_db_ratio': (local_hits / max(total_requests, 1)) * 100,
            'api_dependency_ratio': (misses / max(total_requests, 1)) * 100
        }
    
    def get_system_health(self) -> Dict:
        """Get overall system health status."""
        # Check API usage for all APIs
        api_status = {}
        for api_name in ['trefle', 'plantnet']:
            usage = self.get_api_usage(api_name)
            api_status[api_name] = {
                'healthy': usage['hourly_alert_level'] != 'critical',
                'usage_percentage': usage['hourly_percentage'],
                'alert_level': usage['hourly_alert_level']
            }
        
        # Check cache performance
        cache_perf = self.get_cache_performance()
        cache_healthy = cache_perf['cache_hit_ratio'] > 50  # At least 50% cache hit rate
        
        # Overall system health
        all_apis_healthy = all(status['healthy'] for status in api_status.values())
        
        return {
            'overall_health': 'healthy' if all_apis_healthy and cache_healthy else 'degraded',
            'apis': api_status,
            'cache_performance': {
                'healthy': cache_healthy,
                'hit_ratio': cache_perf['cache_hit_ratio']
            },
            'recommendations': self._get_health_recommendations(api_status, cache_perf)
        }
    
    def get_alerts(self) -> List[Dict]:
        """Get current system alerts."""
        alerts = []
        
        # Check API usage alerts
        for api_name in ['trefle', 'plantnet']:
            usage = self.get_api_usage(api_name)
            
            if usage['hourly_alert_level'] in ['warning', 'critical']:
                alerts.append({
                    'type': 'api_usage',
                    'level': usage['hourly_alert_level'],
                    'api': api_name,
                    'message': f"{api_name.title()} API usage at {usage['hourly_percentage']:.1f}% of hourly limit",
                    'current_usage': usage['hourly_calls'],
                    'limit': usage['hourly_limit']
                })
        
        # Check cache performance alerts
        cache_perf = self.get_cache_performance()
        if cache_perf['cache_hit_ratio'] < 30:  # Less than 30% cache hit rate
            alerts.append({
                'type': 'cache_performance',
                'level': 'warning',
                'message': f"Low cache hit ratio: {cache_perf['cache_hit_ratio']:.1f}%",
                'recommendation': "Consider cache warming or optimization"
            })
        
        if cache_perf['api_dependency_ratio'] > 70:  # More than 70% API dependency
            alerts.append({
                'type': 'api_dependency',
                'level': 'warning',
                'message': f"High API dependency: {cache_perf['api_dependency_ratio']:.1f}%",
                'recommendation': "Increase local database coverage"
            })
        
        return alerts
    
    def _get_alert_level(self, percentage: float) -> str:
        """Get alert level based on usage percentage."""
        if percentage >= self.ALERT_THRESHOLDS['critical'] * 100:
            return 'critical'
        elif percentage >= self.ALERT_THRESHOLDS['warning'] * 100:
            return 'warning'
        else:
            return 'normal'
    
    def _get_health_recommendations(self, api_status: Dict, cache_perf: Dict) -> List[str]:
        """Get health improvement recommendations."""
        recommendations = []
        
        # API usage recommendations
        for api_name, status in api_status.items():
            if status['alert_level'] == 'critical':
                recommendations.append(f"Immediate action required: {api_name} API usage critical")
            elif status['alert_level'] == 'warning':
                recommendations.append(f"Consider reducing {api_name} API calls")
        
        # Cache recommendations
        if cache_perf['cache_hit_ratio'] < 50:
            recommendations.append("Improve cache strategy - consider cache warming")
        
        if cache_perf['local_db_ratio'] < 30:
            recommendations.append("Increase local database coverage with common species")
        
        if cache_perf['api_dependency_ratio'] > 60:
            recommendations.append("Reduce API dependency through better local data")
        
        return recommendations
    
    def export_metrics(self, hours: int = 24) -> Dict:
        """
        Export detailed metrics for analysis.
        
        Args:
            hours: Number of hours of data to export
            
        Returns:
            Dictionary with detailed metrics
        """
        metrics = {
            'export_timestamp': timezone.now().isoformat(),
            'hours_covered': hours,
            'api_usage': {},
            'cache_performance': self.get_cache_performance(),
            'system_health': self.get_system_health(),
            'alerts': self.get_alerts()
        }
        
        # Get API usage for each API
        for api_name in ['trefle', 'plantnet']:
            metrics['api_usage'][api_name] = self.get_api_usage(api_name)
        
        return metrics
    
    def reset_metrics(self, confirm: bool = False):
        """
        Reset all monitoring metrics (use with caution).
        
        Args:
            confirm: Must be True to actually reset
        """
        if not confirm:
            raise ValueError("Must confirm reset by passing confirm=True")
        
        # Clear all monitoring cache keys
        for key_base in self.CACHE_KEYS.values():
            # Delete keys with various suffixes
            for suffix in ['', ':redis', ':local']:
                cache.delete(f"{key_base}{suffix}")
        
        # Clear recent calls
        for api_name in ['trefle', 'plantnet']:
            cache.delete(f"monitor:{api_name}:recent")
        
        logger.warning("All monitoring metrics have been reset")
    
    def log_performance_summary(self):
        """Log a summary of current performance metrics."""
        health = self.get_system_health()
        cache_perf = self.get_cache_performance()
        
        logger.info(f"System Health: {health['overall_health']}")
        logger.info(f"Cache Hit Ratio: {cache_perf['cache_hit_ratio']:.1f}%")
        logger.info(f"Local DB Ratio: {cache_perf['local_db_ratio']:.1f}%")
        logger.info(f"API Dependency: {cache_perf['api_dependency_ratio']:.1f}%")
        
        # Log alerts
        alerts = self.get_alerts()
        for alert in alerts:
            level = alert['level'].upper()
            logger.log(
                logging.WARNING if level == 'WARNING' else logging.ERROR,
                f"[{level}] {alert['message']}"
            )