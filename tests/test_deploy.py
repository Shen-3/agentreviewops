from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).parents[1]


def test_docker_compose_defines_self_hosted_stack() -> None:
    compose = yaml.safe_load((PROJECT_ROOT / "deploy" / "docker-compose.yml").read_text(encoding="utf-8"))

    services = compose["services"]
    assert set(services) == {"postgres", "api", "web"}
    assert services["postgres"]["image"] == "postgres:16-alpine"
    assert services["api"]["environment"]["AGENTREVIEW_DATABASE_URL"].startswith("postgresql+psycopg://")
    assert "/health" in " ".join(str(part) for part in services["api"]["healthcheck"]["test"])
    assert services["web"]["depends_on"]["api"]["condition"] == "service_healthy"
    assert "wget -qO- http://127.0.0.1/" in " ".join(str(part) for part in services["web"]["healthcheck"]["test"])
    assert services["api"]["ports"] == ["8000:8000"]
    assert services["web"]["ports"] == ["8080:80"]
    assert compose["volumes"] == {"postgres-data": None}


def test_api_dockerfile_runs_migrations_before_server() -> None:
    dockerfile = (PROJECT_ROOT / "deploy" / "api.Dockerfile").read_text(encoding="utf-8")

    assert "pip install --no-cache-dir ." in dockerfile
    assert "alembic upgrade head && uvicorn agentreview_api.main:app" in dockerfile


def test_web_dockerfile_builds_static_dashboard_with_api_url() -> None:
    dockerfile = (PROJECT_ROOT / "deploy" / "web.Dockerfile").read_text(encoding="utf-8")
    nginx_conf = (PROJECT_ROOT / "deploy" / "web.nginx.conf").read_text(encoding="utf-8")

    assert "FROM node:22-alpine AS build" in dockerfile
    assert "ARG VITE_AGENTREVIEW_API_URL=http://127.0.0.1:8000" in dockerfile
    assert "npm ci" in dockerfile
    assert "npm run build" in dockerfile
    assert "FROM nginx:1.27-alpine" in dockerfile
    assert "try_files $uri $uri/ /index.html;" in nginx_conf


def test_dockerignore_excludes_heavy_and_secret_local_files() -> None:
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "apps/web/node_modules/" in dockerignore
    assert "apps/web/dist/" in dockerignore
    assert ".env" in dockerignore
    assert "agentreview.db" in dockerignore


def test_ci_runs_python_tests_and_web_build() -> None:
    workflow = yaml.safe_load((PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8"))

    jobs = workflow["jobs"]
    assert "python-test" in jobs
    assert "web-build" in jobs

    python_steps = jobs["python-test"]["steps"]
    assert any(step.get("run") == 'python -m pip install -e ".[dev]"' for step in python_steps)
    assert any(step.get("run") == "pytest" for step in python_steps)

    web_steps = jobs["web-build"]["steps"]
    assert any(step.get("uses") == "actions/setup-node@v4" for step in web_steps)
    assert any(step.get("working-directory") == "apps/web" and step.get("run") == "npm ci" for step in web_steps)
    assert any(step.get("working-directory") == "apps/web" and step.get("run") == "npm run build" for step in web_steps)
