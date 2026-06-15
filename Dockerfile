#checkov:skip=CKV_DOCKER_2:Healthcheck managed by Azure App Service
#checkov:skip=CKV_DOCKER_3:Container runs as default user in App Service sandbox
ARG REGISTRY
FROM ${REGISTRY}/base/python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY .env .
COPY app.py .
COPY style.py .
COPY .streamlit/ .streamlit/
COPY assets/ assets/
COPY layout/ layout/
COPY src/ src/

ENV PYTHONPATH=.

EXPOSE 8501

CMD ["streamlit", "run", "app.py"]
