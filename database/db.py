"""
database/db.py
----------------
Every line of SQL in this project lives in this one file. app.py never
writes a query directly. Keeping SQL in one place means:
- app.py stays focused on handling HTTP requests, not database details.
- If MySQL were ever swapped for another database, only this file
  would need to change.
- All the places SQL injection could sneak in are together in one file
  that's easy to review, instead of scattered across the codebase.
"""

import logging
from typing import Optional, List, Dict

from mysql.connector import pooling, Error as MySQLError

from config import Config

logger = logging.getLogger(__name__)

# A connection POOL (rather than opening a brand-new connection on
# every request) is created once and reused. Opening a fresh TCP
# connection to MySQL for every page load is slow, and under real
# traffic it can exhaust MySQL's max_connections limit. pool_size=5 is
# comfortably enough for a small app on one machine.
_pool = None


class DatabaseError(Exception):
    """
    Every function below catches MySQL's own exception types and
    re-raises THIS exception instead. That way app.py only ever has to
    catch one exception type to handle "something went wrong with the
    database", instead of knowing about every possible mysql.connector
    error class.
    """
    pass


def init_pool() -> None:
    """
    Creates the pool once, when the Flask app boots (called from
    app.py's create_app()). It's deliberately NOT created at import
    time, so that a missing/wrong .env value produces one clear error
    at startup instead of a confusing failure the first time a request
    happens to need the database.
    """
    global _pool
    try:
        _pool = pooling.MySQLConnectionPool(
    pool_name="weather_pool",
    pool_size=5,
    host=Config.MYSQL_HOST,
    port=Config.MYSQL_PORT,
    user=Config.MYSQL_USER,
    password=Config.MYSQL_PASSWORD,
    database=Config.MYSQL_DATABASE,
    ssl_disabled=False,
    ssl_verify_cert=False,
)
        logger.info("MySQL connection pool created successfully.")
    except MySQLError as e:
        logger.error(f"Could not create MySQL connection pool: {e}")
        raise DatabaseError(
            "Could not connect to MySQL. Check the MySQL credentials in "
            ".env and make sure the MySQL server is actually running."
        ) from e


def get_connection():
    """
    Borrows one connection from the pool. Every caller MUST close it
    in a `finally` block (they all do, below) so it's returned to the
    pool for reuse instead of leaking a connection MySQL thinks is
    still busy.
    """
    if _pool is None:
        raise DatabaseError("Database pool was never initialized.")
    try:
        return _pool.get_connection()
    except MySQLError as e:
        raise DatabaseError(f"Could not obtain a DB connection: {e}") from e


def get_or_create_city(name: str, country: str, lat: float, lon: float) -> int:
    """
    Looks up a city by (name, country). Returns its id if it already
    exists (and bumps search_count), or inserts it if this is the
    first time anyone has searched it.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # %s placeholders - NEVER an f-string or + concatenation here.
        # The MySQL driver escapes these values itself, which is what
        # actually prevents SQL injection. Building the query text by
        # hand with string formatting is the #1 way real apps get
        # SQL-injected.
        cursor.execute(
            "SELECT id FROM cities WHERE name = %s AND country = %s",
            (name, country),
        )
        row = cursor.fetchone()

        if row:
            city_id = row[0]
            cursor.execute(
                "UPDATE cities SET search_count = search_count + 1 WHERE id = %s",
                (city_id,),
            )
        else:
            cursor.execute(
                """INSERT INTO cities (name, country, latitude, longitude)
                   VALUES (%s, %s, %s, %s)""",
                (name, country, lat, lon),
            )
            city_id = cursor.lastrowid  # id MySQL just assigned the new row

        conn.commit()  # nothing is actually persisted until commit() runs
        cursor.close()
        return city_id
    except MySQLError as e:
        conn.rollback()  # undo the half-finished transaction, don't leave it dangling
        raise DatabaseError(f"get_or_create_city failed: {e}") from e
    finally:
        conn.close()  # returns the connection to the pool - does NOT destroy it


def save_weather_record(city_id: int, weather: Dict) -> None:
    """
    Inserts one row into weather_records. This single function is what
    turns every search into permanent "weather history" - it's called
    once per successful lookup from the /api/weather route.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO weather_records
               (city_id, temperature, feels_like, humidity, pressure,
                wind_speed, wind_direction, weather_main,
                weather_description, visibility)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                city_id,
                weather["temperature"],
                weather["feels_like"],
                weather["humidity"],
                weather["pressure"],
                weather["wind_speed"],
                weather["wind_direction"],
                weather["weather_main"],
                weather["weather_description"],
                weather["visibility"],
            ),
        )
        conn.commit()
        cursor.close()
    except MySQLError as e:
        conn.rollback()
        raise DatabaseError(f"save_weather_record failed: {e}") from e
    finally:
        conn.close()


def get_history(limit: int = 20, city: Optional[str] = None) -> List[Dict]:
    """
    Returns the most recent searches, newest first, already JOINed
    against `cities` so the caller gets the city name/country without
    a second round-trip query. The optional `city` filter lets the
    same function power "show me everything" and "show me just Delhi"
    without two separate SQL statements to maintain.
    """
    conn = get_connection()
    try:
        # dictionary=True makes fetchall() return {"column": value}
        # dicts instead of plain tuples, so the Flask route can
        # jsonify() the result directly with no manual re-mapping.
        cursor = conn.cursor(dictionary=True)

        base_query = """
            SELECT c.name, c.country, w.temperature, w.feels_like,
                   w.humidity, w.pressure, w.wind_speed, w.wind_direction,
                   w.weather_main, w.weather_description, w.visibility,
                   w.recorded_at
            FROM weather_records w
            JOIN cities c ON c.id = w.city_id
        """

        if city:
            cursor.execute(
                base_query + " WHERE c.name LIKE %s ORDER BY w.recorded_at DESC LIMIT %s",
                (f"%{city}%", limit),
            )
        else:
            cursor.execute(
                base_query + " ORDER BY w.recorded_at DESC LIMIT %s",
                (limit,),
            )

        rows = cursor.fetchall()
        cursor.close()
        return rows
    except MySQLError as e:
        raise DatabaseError(f"get_history failed: {e}") from e
    finally:
        conn.close()
