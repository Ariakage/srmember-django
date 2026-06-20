# Member System

[![GitHub stars](https://img.shields.io/github/stars/Ariakage/srmember-django?style=flat-square)](https://github.com/Ariakage/srmember-django/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Ariakage/srmember-django?style=flat-square)](https://github.com/Ariakage/srmember-django/network/members)
[![GitHub issues](https://img.shields.io/github/issues/Ariakage/srmember-django?style=flat-square)](https://github.com/Ariakage/srmember-django/issues)
[![License](https://img.shields.io/github/license/Ariakage/srmember-django?style=flat-square)](https://github.com/Ariakage/srmember-django/blob/main/LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Django 6.0+](https://img.shields.io/badge/django-6.0%2B-092E20?style=flat-square&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![uv](https://img.shields.io/badge/package%20manager-uv-261230?style=flat-square)](https://docs.astral.sh/uv/)

A general-purpose internal member system developed with Django. It provides a compact team portal with member profiles, OAuth login, personal Bio pages, quick links, document entries, and admin-managed site settings.

Repository: [GitHub](https://github.com/Ariakage/srmember-django)

## Features

- Member directory with manually configured profiles or OAuth-bound accounts.
- OAuth login flow with lookup-code based user discovery.
- Personal Bio pages with Markdown editing, syntax highlighting, math rendering, and rich Markdown extensions.
- Quick links directory with sorting, enabled/disabled state, pinned entries, descriptions, and new-tab behavior.
- Document directory with title, cover image, description, pinned state, sorting, and optional per-document credentials.
- Admin dashboard powered by `django-unfold`.
- Site settings for brand name, navigation logo, navigation target, support email, footer text, and dashboard copy.
- Light/dark theme support in the frontend.

## Tech Stack

- Python 3.12+
- Django 6.0+
- TailwindCSS
- uv
- Authlib
- django-unfold
- python-markdown, pymdown-extensions, Martor

## Quick Start

Install dependencies:

```bash
uv sync
```

Create local environment variables:

```bash
cp .env.example .env
```

Update `.env` with a Django secret key, allowed hosts, admin credentials, and OAuth settings.

Apply migrations:

```bash
uv run python manage.py migrate
```

Run checks:

```bash
uv run python manage.py check
```

Start the development server:

```bash
uv run python manage.py runserver
```

Open the site at:

```text
http://127.0.0.1:8000/
```

## Environment Variables

The project reads configuration from environment variables. See `.env.example` for the full local template.

Common variables:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_SUPERUSER_USERNAME`
- `DJANGO_SUPERUSER_EMAIL`
- `DJANGO_SUPERUSER_PASSWORD`
- `OAUTH_CLIENT_ID`
- `OAUTH_CLIENT_SECRET`
- `OAUTH_SERVER_METADATA_URL`
- `OAUTH_SCOPE`
- `OAUTH_TOKEN_ENDPOINT_AUTH_METHOD`

Do not commit secrets or real credentials.

## Project Structure

```text
.
├── apps/
│   └── core/              # Main application: views, models, admin, templates, tests
├── media/                 # Local uploaded files, ignored except placeholder
├── srmember/              # Django project package and settings
├── static/                # Project-level static assets
├── templates/             # Shared templates and admin overrides
├── manage.py
├── pyproject.toml
└── uv.lock
```

## Useful Commands

```bash
uv run python manage.py makemigrations
uv run python manage.py migrate
uv run python manage.py test
uv run python manage.py check
uv run python manage.py createsuperuser
```

## Administration

After creating an admin user, visit:

```text
http://127.0.0.1:8000/admin/
```

The admin area can manage:

- Site settings
- Member profiles
- OAuth lookup codes
- Bio profiles
- Quick links
- Document entries and document credentials

## License

This project is released under the license included in [LICENSE](LICENSE).
