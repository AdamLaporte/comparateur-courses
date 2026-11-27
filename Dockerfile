# Image minimale pour une mise en ligne facultative (la démo prévue tourne en local avec uv).
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# opencv (lecture des tickets de caisse) a besoin de ces bibliothèques système.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Dépendances d'abord (mises en cache tant que pyproject.toml et uv.lock ne changent pas).
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY data/demo ./data/demo
COPY data/magasins ./data/magasins

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
