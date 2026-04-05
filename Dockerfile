FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY config ./config
COPY templates ./templates
COPY main.py ./
COPY README.md README.me ./

RUN mkdir -p /app/dist /app/output /app/logs

CMD ["python", "main.py", "daemon", "--config", "config/config.json"]
