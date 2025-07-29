#!/bin/bash

set -e

echo "Starting HackTown scraper at $(date)"

# Configuration
REPO_URL="${GITHUB_REPO_URL}"
REPO_DIR="/repo/better-hacktown"
BRANCH="${GITHUB_BRANCH:-main}"

# Function to setup git credentials
setup_git() {
    echo "Setting up git credentials..."
    git config --global user.name "${GIT_USER_NAME:-HackTown Scraper}"
    git config --global user.email "${GIT_USER_EMAIL:-scraper@hacktown.local}"
    
    # Disable interactive prompts
    git config --global credential.helper ""
    git config --global core.askpass ""
    
    # Setup GitHub token authentication
    if [ -n "$GITHUB_TOKEN" ]; then
        echo "Setting up GitHub token authentication..."
        git config --global credential.helper store
        echo "https://${GITHUB_TOKEN}@github.com" > ~/.git-credentials
        chmod 600 ~/.git-credentials
    else
        echo "ERROR: GITHUB_TOKEN is not set!"
        exit 1
    fi
}

# Function to clone or update repository
setup_repository() {
    echo "Setting up repository..."
    
    # Create authenticated URL
    if [ -n "$GITHUB_TOKEN" ]; then
        # Extract repo path from URL (remove https://github.com/)
        REPO_PATH=$(echo "$REPO_URL" | sed 's|https://github.com/||')
        AUTH_URL="https://${GITHUB_TOKEN}@github.com/${REPO_PATH}"
    else
        echo "ERROR: GITHUB_TOKEN is required"
        exit 1
    fi
    
    if [ ! -d "$REPO_DIR" ]; then
        echo "Cloning repository..."
        git clone "$AUTH_URL" "$REPO_DIR"
    else
        echo "Repository exists, updating..."
        cd "$REPO_DIR"
        
        # Update remote URL with token
        git remote set-url origin "$AUTH_URL"
        
        git fetch origin
        git reset --hard "origin/$BRANCH"
    fi
    
    cd "$REPO_DIR"
    git checkout "$BRANCH"
    git pull origin "$BRANCH"
}

# Function to run the scraper
run_scraper() {
    echo "Running scraper..."
    cd "$REPO_DIR"
    
    # Copy the scraper script from the container to the repo
    cp /app/scrape_hacktown.py .
    
    # Show configuration
    echo "Checking scraper configuration..."
    python3 -c "
import os
ci_env = os.environ.get('CI', 'false').lower() == 'true'
github_actions = os.environ.get('GITHUB_ACTIONS', 'false').lower() == 'true'
force_local = os.environ.get('FORCE_LOCAL_MODE', 'false').lower() == 'true'
is_ci = (ci_env or github_actions) and not force_local
mode = 'CI/Conservative' if is_ci else 'Local Development'
print(f'🔧 Scraper Mode: {mode}')
if not is_ci:
    print('🚀 Running with optimized local settings (5 concurrent requests)')
else:
    print('⚠️  Running with conservative CI settings (1 request at a time)')
"
    
    # Run the scraper
    python scrape_hacktown.py
    
    # Move output files to events directory (if needed)
    mkdir -p events
    if [ -d "output" ]; then
        mv output/*.json events/ 2>/dev/null || true
        rm -rf output
    fi
}

# Function to update cache busting version
update_cache_version() {
    echo "Updating cache version..."
    cd "$REPO_DIR"
    
    VERSION=$(date +%Y%m%d%H%M%S)
    
    # Update cache busting version in index.html
    if [ -f "index.html" ]; then
        sed -i "s/content=\"[0-9.]*\"/content=\"$VERSION\"/" index.html
        sed -i "s/manifest\.json?v=[^\"]*\"/manifest.json?v=$VERSION\"/" index.html
        echo "Updated cache version to: $VERSION"
    fi
}

# Function to commit and push changes
commit_and_push() {
    echo "Checking for changes..."
    cd "$REPO_DIR"
    
    # Ensure we have the authenticated remote URL
    if [ -n "$GITHUB_TOKEN" ]; then
        REPO_PATH=$(echo "$REPO_URL" | sed 's|https://github.com/||')
        AUTH_URL="https://${GITHUB_TOKEN}@github.com/${REPO_PATH}"
        git remote set-url origin "$AUTH_URL"
    fi
    
    git add events/ index.html 2>/dev/null || true
    
    if git diff --staged --quiet; then
        echo "No changes detected, skipping commit"
        return 0
    fi
    
    echo "Changes detected, committing..."
    TIMESTAMP=$(date +'%Y-%m-%d %H:%M:%S')
    git commit -m "Update event data from Docker scraper - $TIMESTAMP"
    
    echo "Pushing changes..."
    git push origin "$BRANCH"
    
    echo "Successfully pushed changes to GitHub"
}

# Main execution
main() {
    echo "=== HackTown Docker Scraper Started ==="
    
    # Validate required environment variables
    if [ -z "$REPO_URL" ]; then
        echo "Error: GITHUB_REPO_URL environment variable is required"
        exit 1
    fi
    
    if [ -z "$GITHUB_TOKEN" ]; then
        echo "Warning: GITHUB_TOKEN not set, push operations may fail"
    fi
    
    # Execute the workflow
    setup_git
    setup_repository
    run_scraper
    update_cache_version
    commit_and_push
    
    echo "=== HackTown Docker Scraper Completed Successfully ==="
}

# Run main function
main "$@"
