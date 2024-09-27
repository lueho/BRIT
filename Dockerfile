FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential binutils libpq-dev libproj-dev gdal-bin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt \
    && rm -rf /tmp/requirements.txt \
    && useradd -U standard_user \
    && install -d -m 0755 -o standard_user -g standard_user /app/staticfiles

WORKDIR /app

USER standard_user:standard_user

COPY --chown=standard_user:standard_user . .

RUN chmod +x *.sh

RUN python manage.py collectstatic --noinput