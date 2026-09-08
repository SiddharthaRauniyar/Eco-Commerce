#!/bin/sh

set -eu

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.development}"

python manage.py migrate --noinput

python manage.py collectstatic --noinput

exec "$@"