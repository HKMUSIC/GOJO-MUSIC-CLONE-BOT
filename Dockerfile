FROM python:3.10-slim-bullseye

# Fix Debian archive sources for old bullseye images
RUN sed -i 's|http://deb.debian.org/debian|http://archive.debian.org/debian|g' /etc/apt/sources.list && \
    sed -i '/security.debian.org/d' /etc/apt/sources.list

# Install git, ffmpeg, aria2, curl, gnupg, and Node.js 18.x
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ffmpeg aria2 curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory and copy bot files
WORKDIR /app
COPY . .

# Upgrade pip and install Python requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Start your bot
CMD ["bash", "start"]
