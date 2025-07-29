# Better HackTown 2025

A modern, Progressive Web App (PWA) for browsing HackTown 2025 events with an improved user experience.

## 🚀 Features

- **Event Scraping**: Asynchronous scraping of HackTown 2025 events from the official API
- **Progressive Web App**: Installable PWA with offline capabilities
- **Responsive Design**: Mobile-first design that works on all devices
- **Real-time Updates**: Automated event data synchronization
- **Fast Performance**: Optimized loading and caching strategies
- **Analytics Integration**: Google Analytics and Tag Manager integration

## 📋 Project Structure

```
better-hacktown/
├── scrape_hacktown.py      # Main scraper script (async)
├── index.html              # PWA frontend
├── service-worker.js       # PWA service worker for offline functionality
├── logo.png               # App logo/icon
├── requirements.txt        # Python dependencies
├── events/                # Scraped event data
│   ├── hacktown_events_*.json  # Daily event files
│   ├── locations.json     # Event locations data
│   └── summary.json       # Event summary statistics
└── README.md              # This file
```

## 🛠️ Installation

### Prerequisites

- Python 3.9+ (for zoneinfo support)
- Modern web browser for PWA features

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd better-hacktown
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the scraper**
   ```bash
   python scrape_hacktown.py
   ```

4. **Serve the web application**
   ```bash
   # Using Python's built-in server
   python -m http.server 8000
   
   # Or using any other static file server
   npx serve .
   ```

5. **Access the application**
   Open your browser and navigate to `http://localhost:8000`

## 🔧 Usage

### Event Scraping

The scraper automatically fetches events from the HackTown 2025 API:

```bash
python scrape_hacktown.py
```

**Features:**
- Concurrent async requests for faster scraping
- Automatic retry logic with exponential backoff
- CI/CD environment detection with conservative settings
- Organized output by date in the `events/` directory
- Location and summary data extraction

### Web Application

The PWA provides an enhanced browsing experience:

- **Install as App**: Use your browser's "Add to Home Screen" feature
- **Offline Access**: Events are cached for offline viewing
- **Mobile Optimized**: Touch-friendly interface
- **Fast Loading**: Optimized assets and caching

## 📊 Data Structure

### Event Files
- `hacktown_events_YYYY-MM-DD.json`: Daily event schedules
- `locations.json`: Venue and location information
- `summary.json`: Event statistics and metadata

### API Integration
The scraper connects to:
```
https://hacktown-2025-ss-v2.api.yazo.com.br/public/schedules
```

## 🔄 Automation

### GitHub Actions Workflow

The project includes an automated GitHub Actions workflow (`.github/workflows/scrape-events.yml`) that keeps event data fresh and the web application updated automatically.

#### Workflow Configuration

**Triggers:**
- **Scheduled**: Runs every hour at minute 0 (`0 * * * *`)
- **Manual**: Can be triggered manually via GitHub Actions UI
- **Push**: Automatically runs when `scrape_hacktown.py` or the workflow file is updated

**Environment:**
- Runs on `ubuntu-latest`
- Uses Python 3.10
- Automatically detects CI environment for conservative scraping settings

#### Workflow Steps

1. **Repository Setup**
   ```yaml
   - Checkout repository with write permissions
   - Set up Python 3.10 environment
   - Install dependencies from requirements.txt
   ```

2. **Event Scraping**
   ```yaml
   - Execute scrape_hacktown.py with CI optimizations
   - Handle output directory management
   - Process all HackTown 2025 event dates
   ```

3. **Cache Management**
   ```yaml
   - Generate timestamp-based cache busting version
   - Update index.html with new version numbers
   - Ensure PWA updates properly in browsers
   ```

4. **Git Operations**
   ```yaml
   - Check for changes in events/ and index.html
   - Commit changes with timestamp
   - Push updates back to repository
   ```

#### Workflow Features

- **Smart Updates**: Only commits when actual changes are detected
- **Cache Busting**: Automatically updates PWA cache versions
- **Error Handling**: Graceful handling of missing files and directories
- **CI Optimization**: Uses conservative scraping settings in GitHub Actions
- **Automated Timestamps**: Commits include execution timestamp

#### Monitoring the Workflow

**GitHub Actions Tab:**
- View workflow runs and their status
- Check logs for scraping progress and errors
- Monitor execution time and success rates

**Repository Updates:**
- Automatic commits appear with "Update event data" messages
- Event files are updated in the `events/` directory
- PWA cache versions are automatically incremented

#### Manual Execution

You can manually trigger the workflow:

1. Go to your repository's **Actions** tab
2. Select **"Scrape Hacktown Events"** workflow
3. Click **"Run workflow"** button
4. Choose the branch (usually `main`)
5. Click **"Run workflow"** to execute

#### Troubleshooting Workflow Issues

**Common Issues:**
- **Permission Errors**: Ensure repository has Actions enabled
- **Rate Limiting**: Workflow uses CI-optimized settings to avoid API limits
- **Commit Failures**: Check if repository protection rules allow Actions to push

**Debugging Steps:**
1. Check the Actions tab for detailed logs
2. Look for error messages in the "Run scraper" step
3. Verify the events directory contains updated files
4. Confirm cache versions are being updated in index.html

### CI/CD Support
The scraper includes CI/CD optimizations:
- Detects CI environments (`CI` or `GITHUB_ACTIONS` env vars)
- Adjusts concurrency and retry settings automatically
- Conservative rate limiting in automated environments

### Alternative Scheduling Options
Consider setting up automated runs using:
- **GitHub Actions**: ✅ Already configured (recommended)
- **Cron Jobs**: For server-based scheduling
- **Cloud Functions**: For serverless automation
- **AWS Lambda**: Event-driven scraping

## 🎨 Customization

### Styling
Modify the CSS in `index.html` to customize the appearance.

### Analytics
Update the Google Analytics and Tag Manager IDs in `index.html`:
```javascript
gtag('config', 'YOUR-GA-ID');
// GTM ID in the Tag Manager script
```

### PWA Configuration
Edit the manifest and service worker for PWA customization:
- App name and description
- Theme colors
- Caching strategies
- Offline behavior

## 🚀 Deployment

### Static Hosting
Deploy to any static hosting service:
- **GitHub Pages**: Automatic deployment from repository

### Automated Scraping
Set up scheduled scraping using:
- **GitHub Actions**: `.github/workflows/scrape.yml`

## 📱 PWA Features

- **Installable**: Add to home screen on mobile devices
- **Offline Support**: Cached events available without internet
- **App-like Experience**: Full-screen mode and native feel
- **Fast Loading**: Service worker caching strategies
- **Responsive**: Works on desktop, tablet, and mobile

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

**Made with ❤️ for the HackTown 2025 community with the assistance of Amazon Q**
