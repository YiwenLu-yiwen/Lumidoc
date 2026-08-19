FROM python:3.11-slim

WORKDIR /app

COPY requirements/service-core.txt /tmp/service-core.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && pip install --no-cache-dir -r /tmp/service-core.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY src/modules/chat/requirements.txt /tmp/module-requirements.txt
RUN pip install --no-cache-dir -r /tmp/module-requirements.txt

COPY src/ /app/src/
COPY scripts/docker_healthcheck.py /app/scripts/docker_healthcheck.py

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["python", "/app/scripts/docker_healthcheck.py", "http://127.0.0.1:8001/healthz"]

CMD ["python", "-m", "src.modules.chat.main"]
