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

load_dotenv()

class Config:
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
    OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"
    OPENWEATHER_GEO_URL = "https://api.openweathermap.org/geo/1.0/direct"
    RAINVIEWER_API_URL = "https://api.rainviewer.com/public/weather-maps.json"

    # --- MySQL (Read from Render Environment or local .env) ---
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "weather_app")
    MYSQL_SSL_CA_PEM = os.getenv("MYSQL_SSL_CA_PEM", "")

    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "False") == "True"
    REQUEST_TIMEOUT_SECONDS = 6

def validate_config():
    if not Config.OPENWEATHER_API_KEY:
        raise RuntimeError("OPENWEATHER_API_KEY is missing.")