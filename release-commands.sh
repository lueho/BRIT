#!/bin/sh

python manage.py collectstatic --noinput --settings=brit.settings.heroku
python manage.py makemigrations
python manage.py migrate
