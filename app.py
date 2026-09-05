"""
app.py
------
The Flask entry point. Every route here is deliberately thin: parse
the request -> call a service/database function -> return
JSON/HTML. All real logic lives in services/ and database/, so this
file stays readable no matter how big the project grows.

Run with:  python app.py
"""

import os
import logging
from flask import Flask, render_template, request, jsonify

from config import Config, validate_config
from database import db
from services import weather_service, radar_service

# --- Logging setup ---
# Done here, at import time, before anything else runs, so every other
# module's `logging.getLogger(__name__)` inherits this configuration.
# Logging to a FILE (not just print()) matters because print() output
# disappears the moment the terminal closes; a log file survives and
# lets you debug something that happened yesterday.
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler(),  # also print to the console
    ],
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """
    An "app factory" function, rather than a bare `app = Flask(...)`
    sitting at module level. This makes the app easier to test later:
    a test file can call create_app() to get a fresh instance instead
    of importing one shared global that every test then pollutes.
    """
    flask_app = Flask(__name__)
    flask_app.config["SECRET_KEY"] = Config.SECRET_KEY

    validate_config()   # fail loudly now if OPENWEATHER_API_KEY is missing
    db.init_pool()       # fail loudly now if MySQL is unreachable

    register_routes(flask_app)
    register_error_handlers(flask_app)
    return flask_app


def register_routes(flask_app: Flask) -> None:

    @flask_app.route("/")
    def index():
        return render_template("index.html")

    @flask_app.route("/history")
    def history_page():
        return render_template("history.html")

    @flask_app.route("/api/weather")
    def api_weather():
        """
        GET /api/weather?city=London

        Returns current conditions + a 5-day forecast for the given
        city, and - as a side effect - saves this lookup into MySQL so
        it shows up later in /history.
        """
        city_name = request.args.get("city", "").strip()
        if not city_name:
            # 400 = the CLIENT sent a bad request (blank city), which
            # is different from a 500 (our server broke). The frontend
            # uses this distinction to decide what message to show.
            return jsonify({"error": "Please enter a city name."}), 400

        place = weather_service.geocode_city(city_name)
        current = weather_service.get_current_weather(place["lat"], place["lon"])
        forecast = weather_service.get_forecast(place["lat"], place["lon"])

        city_id = db.get_or_create_city(
            place["name"], place["country"], place["lat"], place["lon"]
        )
        db.save_weather_record(city_id, current)

        return jsonify({
            "city": place["name"],
            "country": place["country"],
            "lat": place["lat"],
            "lon": place["lon"],
            "current": current,
            "forecast": forecast,
        })

    @flask_app.route("/api/radar")
    def api_radar():
        """GET /api/radar - live precipitation radar frame metadata."""
        return jsonify(radar_service.get_radar_frames())

    @flask_app.route("/api/history")
    def api_history():
        """GET /api/history?limit=20&city=Delhi - past searches."""
        limit = request.args.get("limit", 20, type=int)
        city = request.args.get("city")
        records = db.get_history(limit=limit, city=city)

        # MySQL hands back DECIMAL columns as Python Decimal objects
        # and TIMESTAMP columns as datetime objects - neither is JSON
        # serializable out of the box, so we convert them here before
        # jsonify() ever touches them. Skipping this step is a very
        # common bug: it works fine until the first real DB row shows
        # up, then jsonify() crashes with "Object of type Decimal is
        # not JSON serializable".
        for record in records:
            record["recorded_at"] = record["recorded_at"].isoformat()
            for key in ("temperature", "feels_like", "wind_speed"):
                if record.get(key) is not None:
                    record[key] = float(record[key])

        return jsonify(records)


def register_error_handlers(flask_app: Flask) -> None:
    """
    Centralizes turning our custom exceptions into proper HTTP
    responses. Without this, an uncaught CityNotFoundError would show
    the user a raw Python traceback (or a blank generic error page)
    instead of a clean, specific JSON message the frontend can display
    directly.
    """

    @flask_app.errorhandler(weather_service.CityNotFoundError)
    def handle_city_not_found(e):
        logger.info(f"City not found: {e}")
        return jsonify({"error": str(e)}), 404

    @flask_app.errorhandler(weather_service.WeatherAPIError)
    def handle_weather_api_error(e):
        logger.error(f"Weather API error: {e}")
        # 502 = "the server got an invalid response from an upstream
        # server" - accurate here, since the failure is OpenWeatherMap
        # or RainViewer's, not ours.
        return jsonify({"error": str(e)}), 502

    @flask_app.errorhandler(db.DatabaseError)
    def handle_db_error(e):
        logger.error(f"Database error: {e}")
        # Deliberately vague to the USER (never leak raw SQL error
        # text to the browser), but the full exception was already
        # logged above for whoever is debugging.
        return jsonify({"error": "A database error occurred. Please try again."}), 500

    @flask_app.errorhandler(404)
    def handle_404(e):
        return jsonify({"error": "Resource not found."}), 404

    @flask_app.errorhandler(500)
    def handle_500(e):
        logger.exception("Unhandled server error")
        return jsonify({"error": "Something went wrong on our end."}), 500


app = create_app()

if __name__ == "__main__":
    app.run(debug=Config.DEBUG, host="0.0.0.0", port=5000)
