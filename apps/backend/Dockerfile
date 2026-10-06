FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
COPY constraints.txt .
RUN pip install --no-cache-dir --upgrade pip==26.2.1 \
    && pip install --no-cache-dir -r requirements.txt -c constraints.txt
COPY app ./app
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /app/storage && chown app:app /app/storage
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
