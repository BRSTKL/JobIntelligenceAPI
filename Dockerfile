FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY README.md .
COPY .env.example .
RUN mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import os,sys,urllib.request; url=f'http://127.0.0.1:{os.getenv(\"PORT\", \"8000\")}/healthz'; response=urllib.request.urlopen(url); sys.exit(0 if response.status == 200 else 1)"

CMD ["python", "-m", "app.main"]
