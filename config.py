"""
config.py
---------
Single place for every configuration value the app needs.

WHY THIS FILE EXISTS (instead of writing API keys / passwords directly
inside app.py):
1. Security - if real credentials were typed into app.py and that file
   got pushed to GitHub, anyone could steal your API key or DB
   password from the public commit history.
2. Portability - your laptop, a teammate's laptop, and a real server
   all need different DB passwords / ports. A single config module
   that reads environment variables lets each machine supply its own
   values via a local ".env" file, with zero code changes.

python-dotenv reads the ".env" file (which is git-ignored) and copies
its KEY=VALUE lines into the process environment, so os.getenv() can
see them.
"""

import os
from dotenv import load_dotenv

# Must run BEFORE any os.getenv() call below, otherwise the .env
# values won't exist in os.environ yet.
load_dotenv()


class Config:
    """
    Grouping every setting as a class attribute means other files just
    do `from config import Config` and then `Config.SOME_VALUE`,
    instead of every file calling os.getenv() (and risking a typo in
    the environment variable name in five different places).
    """

    # --- Weather API (OpenWeatherMap) ---
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
    OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"
    OPENWEATHER_GEO_URL = "https://api.openweathermap.org/geo/1.0/direct"

    # --- Radar (RainViewer - free, no API key required at all) ---
    RAINVIEWER_API_URL = "https://api.rainviewer.com/public/weather-maps.json"

    # --- MySQL ---
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "weather_app")

    # --- Flask ---
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "False") == "True"

    # --- Networking ---
    # Every outbound HTTP call in this project shares this timeout, so
    # a slow or hanging third-party API can never freeze the whole
    # Flask server. 6 seconds is generous for a weather API but still
    # fast enough that a user isn't stuck staring at a spinner forever.
    REQUEST_TIMEOUT_SECONDS = 6


def validate_config():
    """
    Called once, when the app starts. Fails immediately with a clear
    message if a required secret is missing, instead of letting the
    server boot successfully and then crash confusingly the moment a
    user makes the first request.
    """
    if not Config.OPENWEATHER_API_KEY:
        raise RuntimeError(
            "OPENWEATHER_API_KEY is missing.\n"
            "Copy .env.example to .env and paste in your free key from "
            "https://openweathermap.org/api"
        )
