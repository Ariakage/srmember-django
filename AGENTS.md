# AGENTS.md

## Project Overview

Project name: **SRMember**

SRMember is a Django-based Python project. The project uses **uv** to manage the Python version, dependencies, and development environment.

This file provides guidance for agents working on this repository.

## Tech Stack

* Language: Python
* Framework: Django
* Frontend styling: TailwindCSS
* Environment and dependency manager: uv
* Main branch: `main`

## Project Architecture

SRMember follows Django's MTV architecture.

Use these top-level directories consistently:

* `srmember/`: global Django project package, including `settings.py`, `urls.py`, `asgi.py`, and `wsgi.py`.
* `apps/`: centralized home for custom Django applications. Do not scatter custom apps in the repository root.
* `static/`: project-level static source files.
* `media/`: local user-uploaded files. Do not commit uploaded content; keep only the placeholder needed to preserve the directory.
* `templates/`: global templates shared across apps.

Each custom app must live under `apps/<app>/` and follow Django app conventions:

* Keep app models in `apps/<app>/models.py`.
* Keep app views in `apps/<app>/views.py`.
* Keep app routes in `apps/<app>/urls.py`.
* Keep app templates under `apps/<app>/templates/<app>/...`.
* Register custom apps in `INSTALLED_APPS` with their full config path, for example `apps.<app>.apps.<AppConfig>`.

When adding a new app, prefer `uv run python manage.py startapp <app> apps/<app>` and then adjust its `AppConfig.name` to `apps.<app>`.

## Environment Rules

Use `uv` for Python version and dependency management.

Prefer commands such as:

```bash
uv sync
uv run python manage.py runserver
uv run python manage.py migrate
uv run python manage.py makemigrations
uv run python manage.py test
```

Do not introduce another Python dependency manager unless explicitly requested.

Do not assume that `pip`, `poetry`, `conda`, or other tools should be used unless the project owner gives a specific instruction.

## Django Development Rules

Follow standard Django project conventions.

When modifying Django models, check whether migrations are required.

When adding or changing views, forms, serializers, templates, middleware, settings, URLs, or management commands, keep the implementation clear and maintainable.

Use TailwindCSS for styling web pages and Django templates unless the project owner explicitly requests a different styling approach.

Avoid hardcoding secrets, credentials, tokens, private keys, or environment-specific values directly in the codebase.

Use environment variables or the existing project configuration pattern when applicable.

## Code Readability and Comments

Write code that is easy to read, understand, and maintain.

Add appropriate comments when they help explain non-obvious logic, business rules, edge cases, or important implementation decisions.

Do not over-comment obvious code. Comments should improve clarity rather than repeat what the code already says.

Prefer clear names, simple structure, and small focused functions so that the code remains maintainable over time.

When adding comments, keep them accurate and update them if the related code changes.

## Planning and Uncertainty

When writing code, making plans, or deciding implementation details, do not guess or infer uncertain requirements.

If anything is unclear, ambiguous, missing, or risky, ask the project owner before continuing.

This includes, but is not limited to:

* Business logic
* Database schema decisions
* Authentication and permission behavior
* API response formats
* Deployment assumptions
* Third-party service choices
* UI or UX behavior
* Data migration strategy
* Security-sensitive behavior

Do not silently make assumptions when the project owner has not provided enough information.

## Code Quality

Keep code readable, consistent, and easy to maintain.

Follow the existing project style.

Prefer simple and explicit solutions over overly complex abstractions.

Add appropriate comments to explain complex logic, but avoid unnecessary comments for self-explanatory code.

Before submitting changes, check the related code paths carefully.

When possible, run relevant checks or tests with `uv run`.

## Testing

Use Django's testing tools unless the project already defines another testing approach.

Common command:

```bash
uv run python manage.py test
```

If tests cannot be run, clearly explain why.

## Commit and Push Rules

Unless there are special instructions, when the project owner asks to push changes, push directly to the repository's `main` branch.

Use a standard Git commit message format.

Preferred format:

```text
<type>(<scope>): <summary>
```

Examples:

```text
feat(member): add member profile model
fix(auth): correct login redirect behavior
docs(project): update AGENTS instructions
refactor(core): simplify settings structure
test(member): add member creation tests
chore(deps): update uv lockfile
```

Common commit types:

* `feat`: new feature
* `fix`: bug fix
* `docs`: documentation-only change
* `style`: formatting or style-only change
* `refactor`: code restructuring without behavior change
* `test`: adding or updating tests
* `chore`: maintenance work
* `build`: build system or dependency changes
* `ci`: CI configuration changes

Before pushing, make sure the branch target is `main` unless the project owner says otherwise.

## Repository Safety

Do not delete important files, rewrite history, force push, or make destructive changes unless explicitly instructed.

Do not expose private credentials, tokens, environment files, or sensitive project data.

If a requested change may be destructive or irreversible, ask for confirmation first.

## Agent Behavior Summary

When working on SRMember:

1. Use uv for Python and Django commands.
2. Follow Django conventions.
3. Ask before making uncertain decisions.
4. Write readable and maintainable code.
5. Add appropriate comments for non-obvious logic.
6. Use standard Git commit messages.
7. Push to `main` when the project owner asks to push, unless told otherwise.
