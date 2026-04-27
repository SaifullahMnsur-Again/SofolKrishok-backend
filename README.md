# SofolKrishok Backend

Django backend for the SofolKrishok platform.

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in the values.
4. Run migrations:

```bash
python manage.py migrate
```

5. Start the server:

```bash
python manage.py runserver
```

## DigitalOcean deployment

This backend is ready to deploy to DigitalOcean App Platform without Docker.

### Required runtime settings

Set these environment variables in DigitalOcean:

- `SECRET_KEY`
- `DEBUG=False`
- `ALLOWED_HOSTS` as a comma-separated list, for example `your-app.ondigitalocean.app,api.yourdomain.com`
- `CSRF_TRUSTED_ORIGINS` as a comma-separated list, for example `https://your-frontend-domain.com`
- `FRONTEND_URL` as the exact frontend origin, for example `https://your-frontend-domain.com`
- `DB_ENGINE=django.db.backends.postgresql`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- `CELERY_BROKER_URL` if you use background tasks
- `CELERY_RESULT_BACKEND` if you use background tasks
- `OPENWEATHER_API_KEY` if weather features are enabled
- `GEMINI_API_KEY` if AI features are enabled
- `SSLCOMMERZ_STORE_ID` and `SSLCOMMERZ_STORE_PASSWORD` if payments are enabled

### DigitalOcean App Platform settings

Use these commands:

- Build command: `python manage.py collectstatic --noinput && python manage.py migrate`
- Run command: `gunicorn sofolkrishok.wsgi:application --bind 0.0.0.0:$PORT`

### PostgreSQL

Use a managed PostgreSQL database on DigitalOcean and copy its connection details into the environment variables above.

If you are setting up PostgreSQL manually, create a database and user, then grant the user access to the database. The backend expects the standard Django PostgreSQL variables instead of a connection URL.

### Redis

Redis is only required if you run Celery or other background jobs.

If you do need Redis:

- Create a managed Redis database on DigitalOcean or another Redis instance
- Set `CELERY_BROKER_URL` to the Redis connection string
- Set `CELERY_RESULT_BACKEND` to the same Redis connection string

If you are not using Celery, Redis is not required.

### ML models

The backend loads ML assets from the local filesystem:

- `ml_models/disease_detection/corn_model.h5`
- `ml_models/disease_detection/potato_model.h5`
- `ml_models/disease_detection/rice_model.h5`
- `ml_models/disease_detection/wheat_model.h5`
- `ml_models/soil_classification/soil_type_model.h5`
- `banglaspeech2text/whisper-base-bn`

These files do not need to go to GitHub if you deploy them directly to a DigitalOcean server.

Recommended approach for a Droplet:

1. Create the droplet and install Python, pip, and system packages needed by TensorFlow, Pillow, and psycopg2.
2. Clone only the code repository onto the droplet.
3. Upload the model folders with `rsync`, `scp`, or SFTP to the same paths expected by the app.
4. Set `DISEASE_MODEL_DIR`, `SOIL_MODEL_PATH`, and `WHISPER_BN_MODEL_PATH` to the absolute paths on the droplet.
5. Run migrations and collect static files.
6. Start the app with Gunicorn behind Nginx or a DigitalOcean load balancer.

Example upload commands from your local machine:

```bash
rsync -avz ml_models/ root@your-droplet:/opt/sofolkrishok/ml_models/
rsync -avz banglaspeech2text/ root@your-droplet:/opt/sofolkrishok/banglaspeech2text/
```

If you use App Platform instead of a Droplet, the models must still be available on the runtime filesystem. In that case, use a persistent volume or another storage strategy that the app can read from at startup.

## Notes

- Static files are served through WhiteNoise.
- Media files should use a persistent storage strategy in production.
- Keep `.env` out of git and store secrets only in DigitalOcean environment variables.
