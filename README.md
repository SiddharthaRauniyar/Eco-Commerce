# Secure Commerce

Secure Commerce is a Django e-commerce platform with a customer storefront,
permission-scoped staff operations, security monitoring, and a versioned JSON
API.

## Start locally

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python manage.py migrate
python manage.py seed_roles
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. Create a local administrator with
`python manage.py createsuperuser` when needed.

## Documentation

- [Operation, staff, installation, and deployment guide](docs/guides/phase-18-operation-guides.md)
- [Architecture](docs/architecture/phase-1-project-planning.md)
- [REST API](docs/api/phase-15-rest-api.md)
- [Production deployment and backup runbook](docs/operations/phase-17-deployment.md)

The production Compose stack requires a real `.env`, a controlled TLS
terminator, SMTP, and backup operations. See the operation guide before
exposing it publicly.
