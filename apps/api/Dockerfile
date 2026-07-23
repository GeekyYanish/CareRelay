FROM python:3.12-slim
WORKDIR /app

# Build context must be the monorepo root (not apps/api) so packages/ is available.
COPY apps/api/pyproject.toml .
RUN pip install --no-cache-dir .
COPY apps/api/app ./app
COPY apps/api/alembic.ini .
COPY apps/api/migrations ./migrations
COPY packages/clinical-rules /packages/clinical-rules
COPY packages/demo-data /packages/demo-data

ENV CLINICAL_RULES_PATH=/packages/clinical-rules/demo_v1.yaml
ENV DEMO_DATA_PATH=/packages/demo-data/scenarios.json

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=${FORWARDED_ALLOW_IPS:-127.0.0.1}"]
