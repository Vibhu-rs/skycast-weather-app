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

    # Debug print to check configuration values
    print(f"--- CONFIG DEBUG --- Host: {MYSQL_HOST} | Port: {MYSQL_PORT} | DB: {MYSQL_DATABASE}")

    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "False") == "True"
    REQUEST_TIMEOUT_SECONDS = 6

def validate_config():
    if not Config.OPENWEATHER_API_KEY:
        raise RuntimeError("OPENWEATHER_API_KEY is missing.")