#!/bin/sh

python manage.py migrate
python manage.py collectstatic --noinput --settings=brit.settings.heroku
