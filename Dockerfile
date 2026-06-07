FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system-level build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 1. Copy ONLY the requirements file first (Crucial for Docker caching)
COPY requirements.txt .

# 2. Install the lightweight CPU version of PyTorch first to skip CUDA overhead
RUN pip install --no-cache-dir torch==2.12.0 --extra-index-url https://download.pytorch.org/whl/cpu

# 3. Install the remaining Django and AI dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the actual application source code last
COPY . .

# 5. Compile static administrative layout maps
RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "sofolkrishok.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]