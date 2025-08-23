FROM nikolaik/python-nodejs:python3.10-nodejs19

# Fix expired Debian Buster repos
RUN echo "deb http://archive.debian.org/debian buster main contrib non-free" > /etc/apt/sources.list && \
    echo "deb-src http://archive.debian.org/debian buster main contrib non-free" >> /etc/apt/sources.list && \
    apt-get -o Acquire::Check-Valid-Until=false update && \
    apt-get install -y --no-install-recommends ffmpeg aria2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app/
WORKDIR /app/

# Install Python dependencies
RUN python -m pip install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir --upgrade --requirement requirements.txt

# Start command
CMD ["bash", "start"]
