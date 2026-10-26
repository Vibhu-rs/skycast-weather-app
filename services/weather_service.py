"""
services/weather_service.py
-----------------------------
Every call to the OpenWeatherMap API goes through this file. app.py
never calls `requests.get(...)` itself. That separation matters
because:
- All the messy HTTP status codes / JSON key-digging live in one spot.
- If OpenWeatherMap ever changes their response shape, only this file
  needs editing.
- This module can be unit-tested by mocking `requests.get`, with no
  Flask server needed at all (see tests/test_weather_service.py).
"""

import logging
import requests

from config import Config

logger = logging.getLogger(__name__)


class WeatherAPIError(Exception):
    """Base exception for anything that goes wrong talking to the
    weather API (timeouts, bad API key, service outage, etc.)."""
    pass


class CityNotFoundError(WeatherAPIError):
    """
    Raised specifically when geocoding returns zero matches - i.e. the
    USER typed something wrong (a typo, a place that doesn't exist).
    Kept as its own subclass so app.py can return 404 (client's
    mistake) instead of 502 (our server's/OpenWeatherMap's fault) for
    this one case.
    """
    pass


def _raise_for_common_http_errors(response: requests.Response) -> None:
    """
    Shared logic used by every function below: converts requests'
    generic HTTPError into a message that actually tells the user (or
    the developer reading logs) what went wrong, instead of a bare
    "401 Client Error".
    """
    if response.status_code == 401:
        raise WeatherAPIError(
            "Invalid or missing API key. Check OPENWEATHER_API_KEY in your .env file."
        )
    if response.status_code == 429:
        raise WeatherAPIError(
            "Weather API rate limit reached. Wait a minute and try again."
        )
    response.raise_for_status()


def geocode_city(city_name: str) -> dict:
    """
    Turns free-text like "london" or "Springfield" into an exact
    (lat, lon, resolved_name, country).

    WHY GEOCODE FIRST instead of asking the weather endpoint for the
    city by name directly? Names alone are ambiguous - there are
    dozens of "Springfield"s across different countries/states.
    Resolving to lat/lon first guarantees the weather we show, and the
    point the radar map centers on, are the exact same real-world
    place.
    """
    if not city_name or not city_name.strip():
        raise WeatherAPIError("City name cannot be empty.")

    params = {
        "q": city_name.strip(),
        "limit": 1,
        "appid": Config.OPENWEATHER_API_KEY,
    }

    try:
        response = requests.get(
            Config.OPENWEATHER_GEO_URL,
            params=params,
            timeout=Config.REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout as e:
        raise WeatherAPIError("The weather service took too long to respond.") from e
    except requests.exceptions.ConnectionError as e:
        raise WeatherAPIError(
            "Could not reach the weather service. Check your internet connection."
        ) from e

    _raise_for_common_http_errors(response)

    results = response.json()
    if not results:
        # An empty list means OpenWeatherMap understood the request
        # fine but found no matching place - a USER error, not a
        # server error, so it gets its own exception/status code.
        raise CityNotFoundError(f'No city found matching "{city_name}".')

    place = results[0]
    return {
        "lat": place["lat"],
        "lon": place["lon"],
        "name": place["name"],
        "country": place.get("country", "??"),
    }


def search_cities(query: str, limit: int = 5) -> list:
    """
    Autocomplete helper: returns up to `limit` places matching what the
    user has typed so far, e.g. "spring" -> Springfield (Illinois, US),
    Springfield (Missouri, US), ... Unlike geocode_city(), zero matches
    is normal here (the user is mid-typing), so it returns [] instead of
    raising CityNotFoundError.
    """
    if not query or len(query.strip()) < 2:
        return []

    params = {
        "q": query.strip(),
        "limit": limit,
        "appid": Config.OPENWEATHER_API_KEY,
    }

    try:
        response = requests.get(
            Config.OPENWEATHER_GEO_URL,
            params=params,
            timeout=Config.REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout as e:
        raise WeatherAPIError("The weather service took too long to respond.") from e
    except requests.exceptions.ConnectionError as e:
        raise WeatherAPIError(
            "Could not reach the weather service. Check your internet connection."
        ) from e

    _raise_for_common_http_errors(response)

    seen = set()
    places = []
    for place in response.json():
        # The API can return near-duplicates; keep one per name/state/country.
        key = (place["name"], place.get("state"), place.get("country"))
        if key in seen:
            continue
        seen.add(key)
        places.append({
            "name": place["name"],
            "state": place.get("state", ""),
            "country": place.get("country", "??"),
            "lat": place["lat"],
            "lon": place["lon"],
        })
    return places


# US EPA AQI breakpoints (2024): (conc_low, conc_high, aqi_low, aqi_high)
_PM25_BREAKS = [(0.0, 9.0, 0, 50), (9.1, 35.4, 51, 100), (35.5, 55.4, 101, 150),
                (55.5, 125.4, 151, 200), (125.5, 225.4, 201, 300), (225.5, 325.4, 301, 500)]
_PM10_BREAKS = [(0, 54, 0, 50), (55, 154, 51, 100), (155, 254, 101, 150),
                (255, 354, 151, 200), (355, 424, 201, 300), (425, 604, 301, 500)]
_AQI_CATEGORIES = [(50, "Good"), (100, "Moderate"), (150, "Unhealthy for sensitive groups"),
                   (200, "Unhealthy"), (300, "Very unhealthy"), (500, "Hazardous")]


def _sub_index(conc: float, breaks: list) -> int:
    """Linear interpolation of one pollutant's concentration onto the AQI scale."""
    for c_lo, c_hi, i_lo, i_hi in breaks:
        if conc <= c_hi:
            return round((i_hi - i_lo) / (c_hi - c_lo) * (max(conc, c_lo) - c_lo) + i_lo)
    return 500


def get_air_quality(lat: float, lon: float) -> dict:
    """
    Current air pollution for a coordinate. OpenWeatherMap only gives a
    coarse 1-5 index, so we turn its PM2.5 / PM10 readings into the
    widely used US AQI (0-500) - the higher of the two wins, which is
    how the official AQI is defined. It's an estimate from modelled data.
    """
    params = {"lat": lat, "lon": lon, "appid": Config.OPENWEATHER_API_KEY}
    try:
        response = requests.get(
            f"{Config.OPENWEATHER_BASE_URL}/air_pollution",
            params=params,
            timeout=Config.REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout as e:
        raise WeatherAPIError("The weather service took too long to respond.") from e
    except requests.exceptions.ConnectionError as e:
        raise WeatherAPIError(
            "Could not reach the weather service. Check your internet connection."
        ) from e

    _raise_for_common_http_errors(response)

    entries = response.json().get("list") or []
    if not entries:
        raise WeatherAPIError("Air quality data is not available for this location.")

    comps = entries[0]["components"]
    aqi = max(
        _sub_index(round(comps.get("pm2_5", 0), 1), _PM25_BREAKS),
        _sub_index(round(comps.get("pm10", 0)), _PM10_BREAKS),
    )
    level = next(i for i, (top, _) in enumerate(_AQI_CATEGORIES) if aqi <= top)
    return {
        "aqi": aqi,
        "level": level,
        "category": _AQI_CATEGORIES[level][1],
        "pollutants": {k: round(comps.get(k, 0), 1) for k in ("pm2_5", "pm10", "o3", "no2", "so2", "co")},
    }


def get_current_weather(lat: float, lon: float) -> dict:
    """
    Fetches current conditions for a coordinate and flattens
    OpenWeatherMap's nested JSON into a simple dict whose keys match
    our `weather_records` table columns 1:1 - so this dict can be
    passed straight into db.save_weather_record() with zero extra
    translation.
    """
    params = {
        "lat": lat,
        "lon": lon,
        "appid": Config.OPENWEATHER_API_KEY,
        "units": "metric",  # Celsius / m/s / hPa, matching our UI labels
    }

    try:
        response = requests.get(
            f"{Config.OPENWEATHER_BASE_URL}/weather",
            params=params,
            timeout=Config.REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout as e:
        raise WeatherAPIError("The weather service took too long to respond.") from e
    except requests.exceptions.ConnectionError as e:
        raise WeatherAPIError("Could not reach the weather service.") from e

    _raise_for_common_http_errors(response)
    data = response.json()

    return {
        "temperature": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "pressure": data["main"]["pressure"],
        "wind_speed": data["wind"]["speed"],
        "wind_direction": data["wind"].get("deg", 0),
        "weather_main": data["weather"][0]["main"],
        "weather_description": data["weather"][0]["description"],
        "visibility": data.get("visibility", 0),
        "icon": data["weather"][0]["icon"],
        "sunrise": data["sys"]["sunrise"],
        "sunset": data["sys"]["sunset"],
    }


def get_forecast(lat: float, lon: float) -> list:
    """
    Returns roughly one forecast entry per day for the next 5 days.
    OpenWeatherMap's free /forecast endpoint returns a reading every 3
    hours (40 entries total for 5 days); slicing every 8th entry
    (8 x 3h = 24h) turns that into a clean daily strip instead of
    overwhelming the UI with 40 rows.
    """
    params = {
        "lat": lat,
        "lon": lon,
        "appid": Config.OPENWEATHER_API_KEY,
        "units": "metric",
    }

    try:
        response = requests.get(
            f"{Config.OPENWEATHER_BASE_URL}/forecast",
            params=params,
            timeout=Config.REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException as e:
        # Catch-all for anything not already handled above (rare DNS
        # issues, etc.) - still translated into OUR exception type so
        # app.py only ever needs to catch WeatherAPIError.
        raise WeatherAPIError("Could not fetch forecast data.") from e

    _raise_for_common_http_errors(response)
    data = response.json()

    daily_slice = data["list"][::8]  # every 8th 3-hour slot ~= once per day
    return [
        {
            "datetime": entry["dt_txt"],
            "temperature": entry["main"]["temp"],
            "weather_main": entry["weather"][0]["main"],
            "icon": entry["weather"][0]["icon"],
        }
        for entry in daily_slice
    ]
