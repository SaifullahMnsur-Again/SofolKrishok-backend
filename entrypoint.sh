#!/bin/bash
set -e

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Start Gunicorn
echo "Starting Gunicorn server..."
exec gunicorn sofolkrishok.wsgi:application --bind 0.0.0.0:8000 --workers 3
