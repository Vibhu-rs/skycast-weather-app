# Deploying SkyCast to Render with Aiven MySQL

## Runtime and commands

- Python version: `3.12` (selected by `.python-version`)
- Build command: `python -m pip install --upgrade pip && python -m pip install -r requirements.txt`
- Start command: `python -m gunicorn app:app --workers 1 --threads 4 --timeout 120`

The included `render.yaml` contains the same build and start commands.

## Required Render environment variables

Set these in Render's Environment page. Do not commit real credentials.

- `OPENWEATHER_API_KEY`: your OpenWeatherMap API key
- `FLASK_SECRET_KEY`: a long random secret
- `MYSQL_HOST`: hostname from Aiven
- `MYSQL_PORT`: port from Aiven
- `MYSQL_USER`: Aiven database username
- `MYSQL_PASSWORD`: Aiven database password
- `MYSQL_DATABASE`: database name from Aiven (for this service, `defaultdb`)
- `MYSQL_SSL_CA_PEM`: paste the full Aiven CA certificate, including the BEGIN/END CERTIFICATE lines

The application writes the supplied CA text to `/tmp/skycast-aiven-ca.pem` at startup and enables certificate and hostname verification. Do not paste the database password into `MYSQL_SSL_CA_PEM`.

## Database schema

If this is a new database, run the SQL in `database/schema.sql` against your Aiven MySQL database before using the history features.

## Deploy

Push the project to GitHub, then trigger a deploy in Render. Confirm the build log installs the dependencies and the runtime log reports successful MySQL pool initialization. A successful build alone does not prove that database credentials/network access are correct.
