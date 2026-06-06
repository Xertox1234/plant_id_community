"""
Plant identification service availability/status reporting.

Reports whether the PlantNet and Trefle API clients are configured and reachable.
The user-facing synchronous identification flow lives in
``CombinedPlantIdentificationService`` (the ``/identify/`` endpoint); the legacy
``/requests/`` processing methods (``identify_plant_from_request`` and helpers)
were removed on 2026-06-03 when that stack was retired.
"""

import logging
from typing import Dict

from .plantnet_service import PlantNetAPIService
from .trefle_service import TrefleAPIService

logger = logging.getLogger(__name__)


class PlantIdentificationService:
    """
    Main service for plant identification that combines multiple data sources.
    """

    def __init__(self):
        """Initialize the identification service with API clients."""
        try:
            self.trefle = TrefleAPIService()
        except ValueError:
            logger.warning("Trefle API not available - continuing without it")
            self.trefle = None

        try:
            self.plantnet = PlantNetAPIService()
        except ValueError:
            logger.warning("PlantNet API not available - continuing without it")
            self.plantnet = None

        if not self.trefle and not self.plantnet:
            logger.error("No plant identification APIs available")

    def get_service_status(self) -> Dict:
        """
        Get status of all plant identification services.

        Returns:
            Dictionary with service status information
        """
        status = {
            "trefle": {"available": False},
            "plantnet": {"available": False},
            "combined_service": {"available": False},
        }

        if self.trefle:
            status["trefle"] = self.trefle.get_service_status()

        if self.plantnet:
            status["plantnet"] = self.plantnet.get_service_status()

        # Combined service is available if at least one API works
        status["combined_service"]["available"] = (
            status["trefle"].get("status") == "available"
            or status["plantnet"].get("status") == "available"
        )

        return status
