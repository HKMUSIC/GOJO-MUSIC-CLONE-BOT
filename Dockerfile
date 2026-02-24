FROM python:3.10-slim

# System deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    git \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

CMD ["python3", "-m", "Clonify"]
