#!/bin/sh

set -e
set -x

echo "--- Starting release commands ---"

python manage.py migrate --noinput

echo "--- Release commands finished ---"
