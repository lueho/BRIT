FROM python:3.9

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update \
    && apt-get install -y --fix-missing binutils libproj-dev gdal-bin

COPY ../../requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

WORKDIR /app

COPY . /app