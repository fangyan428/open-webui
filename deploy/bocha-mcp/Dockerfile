FROM python:3.12-slim-bookworm

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir \
    "httpx==0.28.1" \
    "mcp==1.27.2" \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app

COPY server.py /app/server.py

USER app
WORKDIR /app
EXPOSE 8000

ENTRYPOINT ["python", "/app/server.py"]
