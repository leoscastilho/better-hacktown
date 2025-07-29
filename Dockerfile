FROM python:3.11-slim

# Install git for repository operations
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the scraper script
COPY scrape_hacktown.py .
COPY docker-scraper.sh .

# Make the script executable
RUN chmod +x docker-scraper.sh

# Create a directory for the git repository
RUN mkdir -p /repo

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV GIT_TERMINAL_PROMPT=0
ENV GIT_ASKPASS=echo

# Run the scraper script
CMD ["/app/docker-scraper.sh"]
