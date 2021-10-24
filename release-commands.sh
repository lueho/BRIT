#!/bin/sh

python manage.py migrate
python manage.py collectstatic --noinput --settings=flexibi_dst.settings.heroku
