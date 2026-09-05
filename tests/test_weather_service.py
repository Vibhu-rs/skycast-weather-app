"""
tests/test_weather_service.py
-------------------------------
A small example of testing services/weather_service.py WITHOUT making
real network calls. We use unittest.mock.patch to replace
requests.get with a fake version that returns canned data, so these
tests run instantly, never fail because of internet issues, and never
burn real OpenWeatherMap API quota.

Run with:  python -m pytest tests/
       or: python -m unittest tests/test_weather_service.py
"""

import unittest
from unittest.mock import patch, MagicMock

from services import weather_service


class FakeResponse:
    """A minimal stand-in for requests.Response - just enough of the
    interface (status_code, .json(), .raise_for_status()) for the
    functions under test to work with."""

    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise weather_service.requests.exceptions.HTTPError(
                f"{self.status_code} error"
            )


class TestGeocodeCity(unittest.TestCase):

    @patch("services.weather_service.requests.get")
    def test_returns_first_match(self, mock_get):
        mock_get.return_value = FakeResponse([
            {"lat": 28.6139, "lon": 77.2090, "name": "Delhi", "country": "IN"}
        ])

        result = weather_service.geocode_city("Delhi")

        self.assertEqual(result["name"], "Delhi")
        self.assertEqual(result["country"], "IN")
        self.assertAlmostEqual(result["lat"], 28.6139)

    @patch("services.weather_service.requests.get")
    def test_raises_city_not_found_on_empty_results(self, mock_get):
        mock_get.return_value = FakeResponse([])  # OpenWeatherMap found nothing

        with self.assertRaises(weather_service.CityNotFoundError):
            weather_service.geocode_city("Notarealplace123")

    def test_raises_on_blank_input(self):
        with self.assertRaises(weather_service.WeatherAPIError):
            weather_service.geocode_city("   ")


class TestGetCurrentWeather(unittest.TestCase):

    @patch("services.weather_service.requests.get")
    def test_flattens_response_correctly(self, mock_get):
        mock_get.return_value = FakeResponse({
            "main": {"temp": 31.2, "feels_like": 34.0, "humidity": 55, "pressure": 1008},
            "wind": {"speed": 3.6, "deg": 210},
            "weather": [{"main": "Clear", "description": "clear sky", "icon": "01d"}],
            "visibility": 10000,
            "sys": {"sunrise": 1710000000, "sunset": 1710040000},
        })

        result = weather_service.get_current_weather(28.6139, 77.2090)

        self.assertEqual(result["temperature"], 31.2)
        self.assertEqual(result["humidity"], 55)
        self.assertEqual(result["weather_main"], "Clear")


if __name__ == "__main__":
    unittest.main()
