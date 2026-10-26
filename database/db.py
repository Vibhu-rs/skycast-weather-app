import logging
from mysql.connector import pooling
from config import Config

logger = logging.getLogger(__name__)
_pool = None

class DatabaseError(Exception):
    pass

def init_pool():
    global _pool
    try:
        logger.info(f"Attempting to connect to MySQL at {Config.MYSQL_HOST}:{Config.MYSQL_PORT}...")
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
        logger.info("MySQL connection pool created successfully!")
    except Exception as e:
        logger.error(f"DETAILED MYSQL ERROR: {e}")
        raise DatabaseError(f"Could not connect to MySQL: {e}") from e


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
