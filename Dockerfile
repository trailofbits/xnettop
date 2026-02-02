FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpcap-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY . .

RUN uv sync --frozen --no-dev

ENTRYPOINT ["uv", "run", "xnettop"]
