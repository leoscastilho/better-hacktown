# Docker Scraper Setup Guide

This guide will help you set up the HackTown scraper to run on your home server using Docker, replacing the GitHub Actions workflow.

## Prerequisites

- Docker and Docker Compose installed on your home server
- A GitHub Personal Access Token
- Access to your server's crontab

## Setup Steps

### 1. Create GitHub Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a descriptive name like "HackTown Docker Scraper"
4. Select the following permissions:
   - `repo` (Full control of private repositories)
5. Copy the generated token (you won't see it again!)

### 2. Configure Environment Variables

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file:
   ```bash
   nano .env
   ```

3. Update the following values:
   - `GITHUB_REPO_URL`: Replace `YOUR_USERNAME` with your GitHub username
   - `GITHUB_TOKEN`: Paste your GitHub Personal Access Token
   - Optionally update `GIT_USER_NAME` and `GIT_USER_EMAIL`

### 3. Make Scripts Executable

```bash
chmod +x run-scraper.sh
chmod +x docker-scraper.sh
```

### 4. Test the Setup

Run the full scraper test:

```bash
./run-scraper.sh
```

Check the logs:
```bash
tail -f logs/scraper-$(date +%Y%m%d).log
```

### 5. Set Up Cron Job

Add a cron job to run the scraper every hour:

```bash
crontab -e
```

Add this line to run every hour:
```bash
0 * * * * /path/to/your/better-hacktown/run-scraper.sh >/dev/null 2>&1
```

Or if you want to run every 30 minutes:
```bash
*/30 * * * * /path/to/your/better-hacktown/run-scraper.sh >/dev/null 2>&1
```

## Performance Modes

The scraper has two performance modes:

### Local Development Mode (Default for Docker)
- **Concurrent Requests**: 5 simultaneous requests
- **Request Delays**: 0.5-1.5 seconds between requests
- **Retry Delays**: 5-10 seconds
- **Optimized for**: Speed and efficiency

### CI Mode (GitHub Actions)
- **Concurrent Requests**: 1 request at a time
- **Request Delays**: 5-12 seconds between requests
- **Retry Delays**: 20+ seconds
- **Optimized for**: API respect and avoiding rate limits

The Docker setup uses `FORCE_LOCAL_MODE=true` to ensure optimal performance on your home server.

## Monitoring

### View Logs
```bash
# View today's log
tail -f logs/scraper-$(date +%Y%m%d).log

# View all recent logs
ls -la logs/

# View specific date
cat logs/scraper-20250729.log
```

### Check Container Status
```bash
# View running containers
docker ps

# View all containers (including stopped)
docker ps -a

# View container logs
docker logs hacktown-scraper
```

### Manual Run
```bash
# Run manually
./run-scraper.sh

# Run with Docker Compose directly
docker-compose up --build hacktown-scraper

# Run and follow logs
docker-compose up --build hacktown-scraper --follow
```

## Troubleshooting

### Common Issues

1. **Git Authentication Error: "could not read Username"**
   - This means the GitHub token authentication failed
   - Run `./test-github-auth.sh` to diagnose the issue
   - Common causes:
     - GitHub token not set in `.env` file
     - Invalid or expired GitHub token
     - Token doesn't have `repo` permissions
     - Repository URL is incorrect

2. **Permission Denied on GitHub Push**
   - Check your GitHub token has `repo` permissions
   - Verify the token is correctly set in `.env`
   - Make sure the token has access to the repository

3. **Container Build Fails**
   - Make sure Docker is running
   - Check if all files are present
   - Try: `docker-compose build --no-cache`

4. **Git Authentication Issues**
   - Verify your GitHub token is valid
   - Check the repository URL is correct
   - Ensure the token has access to the repository
   - Run the authentication test: `./test-github-auth.sh`

5. **Cron Job Not Running**
   - Check cron service is running: `systemctl status cron`
   - Verify the path in crontab is absolute
   - Check cron logs: `grep CRON /var/log/syslog`

### Debug Mode

To run with more verbose output:

```bash
# Set debug mode
export DEBUG=1
./run-scraper.sh
```

### Clean Reset

If you need to start fresh:

```bash
# Remove containers and volumes
docker-compose down -v
docker system prune -f

# Remove logs
rm -rf logs/

# Run again
./run-scraper.sh
```

## Resource Usage

The container is configured with resource limits:
- Memory: 512MB
- CPU: 0.5 cores

You can adjust these in `docker-compose.yml` if needed.

## Security Notes

- Keep your `.env` file secure and never commit it to git
- The GitHub token has repository access, so protect it
- Consider using a dedicated GitHub account for the scraper
- Regularly rotate your GitHub tokens

## Maintenance

- Logs are automatically cleaned up (kept for 7 days)
- Old containers are automatically removed
- The git repository is persisted in a Docker volume
- Consider backing up the Docker volume periodically
