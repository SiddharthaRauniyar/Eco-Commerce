FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 commerce \
    && useradd --uid 10001 --gid commerce --create-home commerce

COPY --chown=commerce:commerce . .

RUN pip install --no-cache-dir . \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R commerce:commerce /app \
    && chmod 500 /app/infra/entrypoint.sh

USER commerce

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD ["python", "-c", "import os; from urllib.request import Request, urlopen; port=os.environ.get('PORT','8000'); host=os.environ['DJANGO_ALLOWED_HOSTS'].split(',',1)[0].strip(); assert urlopen(Request(f'http://127.0.0.1:{port}/health/', headers={'Host':host,'X-Forwarded-Proto':'https'}), timeout=5).status == 200"]

ENTRYPOINT ["/app/infra/entrypoint.sh"]

CMD ["gunicorn", "--config", "config/gunicorn.conf.py", "config.wsgi:application"]