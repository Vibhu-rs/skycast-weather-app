-- schema.sql
-- ----------
-- Run this once to create the database and tables:
--   mysql -u root -p < database/schema.sql
--
-- DESIGN NOTE: why two tables instead of one flat "history" table?
-- If every search stored the city's name/country/lat/lon directly on
-- each row, searching "Delhi" 50 times would repeat the exact same
-- text/coordinates 50 times. Instead we store each city ONCE in
-- `cities`, and every weather lookup becomes a row in
-- `weather_records` that just points back to that city's id. This is
-- basic normalization: it keeps the data small, keeps `cities` easy
-- to index, and means a bug fixing one city's coordinates only needs
-- one UPDATE, not fifty.

CREATE DATABASE IF NOT EXISTS weather_app
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE weather_app;

CREATE TABLE IF NOT EXISTS cities (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    country       VARCHAR(10)  NOT NULL,
    latitude      DECIMAL(9,6) NOT NULL,
    longitude     DECIMAL(9,6) NOT NULL,
    -- Bumped every time someone searches this city again. Lets a
    -- future "trending cities" feature be a one-line ORDER BY.
    search_count  INT DEFAULT 1,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Prevents "London, GB" from ever being inserted twice.
    UNIQUE KEY unique_city (name, country)
);

CREATE TABLE IF NOT EXISTS weather_records (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    city_id               INT NOT NULL,
    temperature           DECIMAL(5,2),   -- Celsius, e.g. 27.34
    feels_like            DECIMAL(5,2),
    humidity              INT,            -- percent, 0-100
    pressure              INT,            -- hPa
    wind_speed            DECIMAL(5,2),   -- m/s
    wind_direction        INT,            -- degrees, 0-360
    weather_main          VARCHAR(50),    -- e.g. "Rain"
    weather_description   VARCHAR(150),   -- e.g. "light rain"
    visibility            INT,            -- meters
    recorded_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE CASCADE,

    -- History queries always sort/filter by time, so this index keeps
    -- "give me the last 20 searches" fast even with a huge table.
    INDEX idx_recorded_at (recorded_at)
);
