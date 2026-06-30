from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_dockerfiles_use_public_base_images() -> None:
    backend_dockerfile = (REPO_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    frontend_dockerfile = (REPO_ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:" in backend_dockerfile
    assert "FROM node:" in frontend_dockerfile
    assert "my-project-backend" not in backend_dockerfile
    assert "my-project-frontend" not in frontend_dockerfile


def test_frontend_dockerfile_uses_lockfile_install() -> None:
    frontend_dockerfile = (REPO_ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY package.json package-lock.json" in frontend_dockerfile
    assert "RUN npm ci" in frontend_dockerfile
