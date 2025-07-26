FROM python:3.10-slim-bullseye

# Install git, ffmpeg, and aria2
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ffmpeg aria2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory and copy files
WORKDIR /app
COPY . .

# Upgrade pip and install requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Start the bot
CMD ["bash", "start"]
