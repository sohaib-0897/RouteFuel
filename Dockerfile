FROM node:22-bookworm-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY manage.py ./
COPY config/ ./config/
COPY routes/ ./routes/
COPY data/ ./data/
COPY fuel-prices-for-be-assessment.csv ./
COPY --from=frontend-build /frontend/dist /app/frontend/dist
RUN DJANGO_SECRET_KEY=build-only-placeholder python manage.py collectstatic --noinput \
    && useradd --create-home appuser \
    && mkdir -p /app/.cache/django \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "120", "--access-logfile", "-"]
