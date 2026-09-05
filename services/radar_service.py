"""
services/radar_service.py
---------------------------
RainViewer's public API requires no signup and no API key, which is
why it's used for the "live radar" feature instead of a paid radar
provider. It returns metadata (a host + a list of timestamped paths);
the BROWSER (in main.js) turns that metadata into actual map tile URLs
and overlays them on the Leaflet map. This file just fetches and
forwards that metadata.
"""

import logging
import requests

from config import Config
from services.weather_service import WeatherAPIError

logger = logging.getLogger(__name__)


def get_radar_frames() -> dict:
    """
    Returns RainViewer's frame list almost unmodified, because Leaflet
    needs the exact `host` and frame `path` strings RainViewer provides
    to build valid tile URLs - reshaping the data here would just mean
    reshaping it back in JavaScript for no benefit.
    """
    try:
        response = requests.get(
            Config.RAINVIEWER_API_URL,
            timeout=Config.REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # Radar is a "nice to have" layered on top of core weather
        # data. We log it and raise a clearly-labeled error rather
        # than letting a third-party radar outage look like our whole
        # app is broken.
        logger.warning(f"Radar service unavailable: {e}")
        raise WeatherAPIError("Radar data is temporarily unavailable.") from e

    data = response.json()
    return {
        "host": data["host"],
        "past_frames": data["radar"]["past"],
        "nowcast_frames": data["radar"].get("nowcast", []),
    }
