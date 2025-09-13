FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NLTK_DATA=/usr/local/share/nltk_data

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY . /app

COPY requirements.txt /app/
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# Pre-download NLTK data into NLTK_DATA
RUN python - <<'PY'
import nltk, os
target = os.environ.get('NLTK_DATA', '/usr/local/share/nltk_data')
os.makedirs(target, exist_ok=True)
nltk.download('wordnet', download_dir=target)
nltk.download('omw-1.4', download_dir=target)
PY

RUN apt-get purge -y --auto-remove build-essential \
 && rm -rf /var/lib/apt/lists/* /root/.cache/pip
RUN useradd --create-home appuser \
 && chown -R appuser:appuser /app /usr/local/share/nltk_data
USER appuser

EXPOSE 8000

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "app:app", "-w", "2", "-b", "0.0.0.0:8000", "--log-level", "info"]
