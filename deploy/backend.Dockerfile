FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend /app/backend
RUN pip install --no-cache-dir /app/backend
USER 65532:65532
EXPOSE 8080

