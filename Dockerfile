ARG PYTHON_BASE=python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
FROM ${PYTHON_BASE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock && mkdir /channel && chown 10001:10001 /channel
COPY src/ src/
COPY policies/ policies/
COPY tests/ tests/
COPY pytest.ini .
RUN chmod -R a-w /app && chmod 755 /channel
USER 10001:10001
CMD ["python", "-m", "lab.server"]
