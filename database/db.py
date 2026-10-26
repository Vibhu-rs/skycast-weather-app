"""
database/db.py
----------------
Every line of SQL in this project lives in this one file.
"""

import logging
import os
from pathlib import Path
from typing import Optional, List, Dict

from mysql.connector import pooling, Error as MySQLError

from config import Config

logger = logging.getLogger(__name__)

_pool = None


class DatabaseError(Exception):
    pass


def init_pool():
    """Create the MySQL pool, using Aiven's CA certificate when configured."""
    global _pool
    try:
        if not all((Config.MYSQL_HOST, Config.MYSQL_USER,
                    Config.MYSQL_PASSWORD, Config.MYSQL_DATABASE)):
            raise DatabaseError(
                "MySQL configuration is incomplete. Set MYSQL_HOST, MYSQL_USER, "
                "MYSQL_PASSWORD, and MYSQL_DATABASE in the environment."
            )

        connection_options = {
            "pool_name": "weather_pool",
            "pool_size": 5,
            "host": Config.MYSQL_HOST,
            "port": int(Config.MYSQL_PORT),
            "user": Config.MYSQL_USER,
            "password": Config.MYSQL_PASSWORD,
            "database": Config.MYSQL_DATABASE,
            "ssl_disabled": False,
            "connection_timeout": 15,
            "use_pure": True,
        }

        ca_pem = getattr(Config, "MYSQL_SSL_CA_PEM", "").strip()
        if ca_pem:
            # Keep this file for the lifetime of the process: pooled connections
            # may be created after pool initialization, so don't delete it early.
            ca_path = Path(os.getenv("TMPDIR", "/tmp")) / "skycast-aiven-ca.pem"
            ca_path.write_text(ca_pem.replace("\\n", "\n"), encoding="utf-8")
            connection_options.update({
                "ssl_ca": str(ca_path),
                "ssl_verify_cert": True,
                "ssl_verify_identity": True,
            })
        else:
            # Aiven's SSL mode REQUIRED encrypts traffic, but certificate
            # identity verification is enabled only when the CA is provided.
            connection_options["ssl_verify_cert"] = False

        logger.info(
            "Attempting MySQL connection to %s:%s",
            Config.MYSQL_HOST,
            Config.MYSQL_PORT,
        )
        _pool = pooling.MySQLConnectionPool(**connection_options)
        logger.info("MySQL connection pool created successfully!")
    except Exception as e:
        logger.exception("MySQL pool initialization failed")
        raise DatabaseError(
            f"Could not connect to MySQL: {type(e).__name__}: {e}"
        ) from e


def get_connection():
    if _pool is None:
        raise DatabaseError("Database pool was never initialized.")
    try:
        return _pool.get_connection()
    except MySQLError as e:
        raise DatabaseError(f"Could not obtain a DB connection: {e}") from e


def get_or_create_city(name: str, country: str, lat: float, lon: float) -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
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
            city_id = cursor.lastrowid

        conn.commit()
        cursor.close()
        return city_id
    except MySQLError as e:
        conn.rollback()
        raise DatabaseError(f"get_or_create_city failed: {e}") from e
    finally:
        conn.close()


def save_weather_record(city_id: int, weather: Dict) -> None:
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
    conn = get_connection()
    try:
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