#!/usr/bin/env python3
"""
HackTown 2025 Event Scraper - Asynchronous Version

This script scrapes event data from the HackTown 2025 API using asynchronous HTTP requests
for improved performance. It fetches all events across multiple dates, processes location
data, and saves organized JSON files for use in the web application.

Key Features:
- Asynchronous HTTP requests with concurrent processing
- Automatic retry logic with exponential backoff
- CI/CD environment detection and optimization
- Location normalization and categorization
- Comprehensive error handling and logging
- Data persistence with summary statistics

Author: Generated with assistance from Amazon Q
License: MIT
"""

import asyncio
import aiohttp
import json
import os
import random
from datetime import datetime
import time
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo
import logging

# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

# API endpoint for HackTown 2025 event schedules
BASE_URL = "https://hacktown-2025-ss-v2.api.yazo.com.br/public/schedules"

# Directory where scraped event data will be stored
OUTPUT_DIR = "events"

# ============================================================================
# ENVIRONMENT DETECTION AND ADAPTIVE SETTINGS
# ============================================================================

# Detect if running in CI/CD environment (GitHub Actions, etc.)
# This allows us to use more conservative settings to avoid rate limiting
IS_CI = os.environ.get('CI', 'false').lower() == 'true' or os.environ.get('GITHUB_ACTIONS', 'false').lower() == 'true'

# Adjust concurrency and timing settings based on environment
if IS_CI:
    MAX_CONCURRENT_REQUESTS = 1  # Ultra-conservative: single request at a time in CI
    RETRY_DELAY = 20  # Much longer initial delay between retries in CI (seconds)
    MAX_RETRIES = 3   # Fewer retries in CI to avoid prolonged blocking
    REQUEST_TIMEOUT = 60  # Longer timeout for CI environment
    print("🤖 Running in CI environment - using ultra-conservative settings")
    print(f"   • Max concurrent requests: {MAX_CONCURRENT_REQUESTS}")
    print(f"   • Retry delay: {RETRY_DELAY}s")
    print(f"   • Max retries: {MAX_RETRIES}")
    print(f"   • Request timeout: {REQUEST_TIMEOUT}s")
else:
    MAX_CONCURRENT_REQUESTS = 2  # Local development: allow 2 concurrent requests
    RETRY_DELAY = 5  # Shorter delay for local development (seconds)
    MAX_RETRIES = 5  # More retries for local development
    REQUEST_TIMEOUT = 30  # Standard timeout for local development

# ============================================================================
# EVENT CONFIGURATION
# ============================================================================

# HackTown 2025 event dates to scrape
# These dates correspond to the actual event schedule
EVENT_DATES = [
    "2025-07-30",  # Day 1
    "2025-07-31",  # Day 2
    "2025-08-01",  # Day 3
    "2025-08-02",  # Day 4
    "2025-08-03"   # Day 5
]

# ============================================================================
# HTTP REQUEST HEADERS
# ============================================================================

# HTTP headers required by the HackTown API
# Enhanced headers to better mimic real browser requests and avoid blocking
def get_headers():
    """Generate headers with some randomization to avoid detection"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0'
    ]
    
    return {
        'accept': 'application/json, text/plain, */*',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'en-US,en;q=0.9,pt;q=0.8',
        'cache-control': 'no-cache',
        'origin': 'https://hacktown2025.yazo.app.br',
        'pragma': 'no-cache',
        'product-identifier': '1',
        'referer': 'https://hacktown2025.yazo.app.br/',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'cross-site',
        'user-agent': random.choice(user_agents),
        'x-requested-with': 'XMLHttpRequest'
    }

# Keep a base version for backwards compatibility
HEADERS = get_headers()

# ============================================================================
# LOGGING SETUP
# ============================================================================

# Configure logging with timestamp, level, and message format
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# PROXY CONFIGURATION (Optional - for future use if needed)
# ============================================================================

def get_proxy_list():
    """
    Get list of free proxies for rotation (if needed in the future).
    Currently disabled but can be enabled if API blocking becomes severe.
    """
    # Free proxy services (use with caution in production)
    # return [
    #     'http://proxy1:port',
    #     'http://proxy2:port',
    # ]
    return []

def get_random_proxy():
    """Get a random proxy from the list (currently disabled)"""
    proxies = get_proxy_list()
    return random.choice(proxies) if proxies else None

# ============================================================================
# LOCATION PROCESSING CACHE
# ============================================================================

# Cache for location normalization to avoid repeated processing
# Key: original location string, Value: (filter_location, near_location) tuple
location_cache = {}


def normalize_and_locate(place: str) -> tuple[str, str]:
    """
    Normalize location names and categorize them into filter and proximity groups.
    
    This function processes raw location strings from the API and maps them to:
    1. filterLocation: Standardized location name for filtering/grouping
    2. nearLocation: Broader geographical area for proximity-based grouping
    
    The function uses caching to improve performance for repeated location lookups.
    
    Args:
        place (str): Raw location string from the API
        
    Returns:
        tuple[str, str]: (filter_location, near_location)
        
    Location Categories:
        - "Inatel e Arredores": Campus and nearby venues
        - "ETE e Arredores": Technical school area
        - "Praça e Arredores": Central plaza and downtown area
        - "Other": Unmapped or unknown locations
    """
    # Handle empty or None input
    if not place:
        return "Other", "Other"

    # Check cache first to avoid repeated processing
    if place in location_cache:
        return location_cache[place]

    # Convert to uppercase for case-insensitive matching
    place_upper = place.upper()
    
    # Default values for unmapped locations
    filter_location = "Other"
    near_location = "Other"

    # ========================================================================
    # LOCATION MAPPING RULES
    # ========================================================================
    # Each condition maps venue names to standardized categories
    # The mapping is based on physical proximity and venue characteristics
    
    # INATEL Campus and surrounding area
    if "INATEL" in place_upper:
        filter_location = "Inatel"
        near_location = "Inatel e Arredores"

    # Technical School (ETE) area
    elif "ETE" in place_upper:
        filter_location = "ETE"
        near_location = "ETE e Arredores"

    # Central plaza area venues
    elif "LOJA MAÇONICA" in place_upper or "LOJA MAÇÔNICA" in place_upper:
        filter_location = "Loja Maçônica"
        near_location = "Praça e Arredores"

    elif "REAL PALACE" in place_upper:
        filter_location = "Real Palace"
        near_location = "Praça e Arredores"

    elif "BRASEIRO" in place_upper:
        filter_location = "Braseiro"
        near_location = "Praça e Arredores"

    elif "BOTECO DO TIO" in place_upper:
        filter_location = "Boteco do Tio João"
        near_location = "Praça e Arredores"

    elif "ASSOCIAÇÃO" in place_upper:
        filter_location = "Associação José do Patrocínio"
        near_location = "Praça e Arredores"

    elif "BAR E RESTAURANTE" in place_upper:
        filter_location = "Bar e Restaurante do Dimas II"
        near_location = "Praça e Arredores"

    elif "ESCOLA S" in place_upper:
        filter_location = "Escola Sanico Teles"
        near_location = "Praça e Arredores"

    # INATEL area venues (special event spaces)
    elif "CASA DINAMARCA" in place_upper:
        filter_location = "Casa Dinamarca"
        near_location = "Inatel e Arredores"

    elif "CASA MFM" in place_upper:
        filter_location = "Casa MFM"
        near_location = "Inatel e Arredores"

    elif "CASA DO CCCF" in place_upper:
        filter_location = "Casa do CCCF"
        near_location = "Praça e Arredores"

    # Event stages and special venues
    elif "PALCO UNDERSTREAM" in place_upper:
        filter_location = "Palco UNDERSTREAM"
        near_location = "Praça e Arredores"

    elif "INCUBADORA MUNICIPAL" in place_upper:
        filter_location = "Incubadora Municipal"
        near_location = "Praça e Arredores"

    elif "CASA GOOGLE CLOUD" in place_upper:
        filter_location = "Casa Google Cloud"
        near_location = "Inatel e Arredores"

    elif "CASA FUTUROS POSSÍVEIS" in place_upper:
        filter_location = "Casa Futuros Possíveis - Maria Maria Gastrobar"
        near_location = "Praça e Arredores"

    elif "PALCO MULTIEXPERIÊNCIAS" in place_upper:
        filter_location = "Palco MultiExperiências"
        near_location = "ETE e Arredores"

    elif "CIRCUITO SESC AMANTIKIR" in place_upper:
        filter_location = "Circuito SESC Amantikir"
        near_location = "Praça e Arredores"

    # Restaurants and food venues
    elif "MIMMA" in place_upper:
        filter_location = "Mimma's"
        near_location = "Praça e Arredores"

    elif "DIJA GASTRONOMIA" in place_upper:
        filter_location = "Dija Gastronomia"
        near_location = "Praça e Arredores"

    elif "GRANDPA JOEL" in place_upper or "COFFEE SHOP" in place_upper:
        filter_location = "Grandpa Joel´s Coffee Shop"
        near_location = "Praça e Arredores"

    # Street and area-based locations
    elif "SINHÁ MOREIRA" in place_upper or "SINHA MOREIRA" in place_upper:
        filter_location = "Av. Sinhá Moreira"
        near_location = "ETE e Arredores"

    elif "BE BOLD" in place_upper:
        filter_location = "Be Bold"
        near_location = "ETE e Arredores"

    elif "MERCADO MUNICIPAL" in place_upper:
        filter_location = "Mercado Municipal"
        near_location = "ETE e Arredores"

    elif "FEIRA DA MANTIQUEIRA" in place_upper:
        filter_location = "Feira da Mantiqueira"
        near_location = "Inatel e Arredores"

    # Special cases
    elif "A SER ANUNCIADO" in place_upper:
        filter_location = "A ser anunciado"
        near_location = "ETE e Arredores"

    else:
        # For unmapped locations, preserve the original name
        # This allows for future mapping without losing data
        filter_location = place
        near_location = None

    # Cache the result for future lookups
    result = (filter_location, near_location)
    location_cache[place] = result
    return result


async def fetch_page(session: aiohttp.ClientSession, date: str, page: int) -> Optional[Dict[str, Any]]:
    """
    Fetch a single page of events for a specific date with comprehensive retry logic.
    
    This function handles the core HTTP request to the HackTown API with robust
    error handling, rate limiting, and retry mechanisms to ensure reliable data fetching.
    
    Args:
        session (aiohttp.ClientSession): Reusable HTTP session for connection pooling
        date (str): Event date in YYYY-MM-DD format
        page (int): Page number to fetch (1-based indexing)
        
    Returns:
        Optional[Dict[str, Any]]: JSON response data or None if all retries failed
        
    Error Handling:
        - HTTP 403: Implements exponential backoff retry (common rate limiting response)
        - Timeout: Retries with fixed delay
        - Other HTTP errors: Logged and returned as None
        - Network exceptions: Caught and retried
        
    Rate Limiting:
        - Random delays between requests to appear more human-like
        - Longer delays in CI environments to be more respectful
        - Exponential backoff for 403 errors with jitter
    """
    # Prepare API request parameters
    # These parameters match the official HackTown web app requests
    params = {
        'category_id': '42',           # HackTown 2025 category identifier
        'tag_ids': '[]',               # No tag filtering (empty array)
        'day[]': [date, '00:00:00.000Z'],  # Date filter with timezone
        'page': str(page),             # Current page number
        'search': '',                  # No search query
        'product_ids': '[2]'           # Product identifier for HackTown 2025
    }

    # Retry loop with exponential backoff
    for attempt in range(MAX_RETRIES):
        try:
            # Add random delay to avoid appearing as a bot
            # Much longer delays in CI to be more respectful of the API
            if IS_CI:
                # In CI: longer delays and simulate human browsing patterns
                base_delay = random.uniform(5, 12)  # 5-12 seconds base delay
                if attempt > 0:
                    base_delay += random.uniform(10, 20)  # Additional delay on retries
                await asyncio.sleep(base_delay)
            else:
                await asyncio.sleep(random.uniform(0.5, 1.5))  # 0.5-1.5 seconds locally
            
            # Get fresh headers for each request to avoid fingerprinting
            headers = get_headers()
            
            # Make the HTTP request with timeout
            async with session.get(
                    BASE_URL,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                
                # Success case: return parsed JSON
                if response.status == 200:
                    logger.info(f"✅ Successfully fetched {date} page {page}")
                    return await response.json()
                
                # Rate limiting case: retry with exponential backoff
                elif response.status == 403 and attempt < MAX_RETRIES - 1:
                    logger.warning(f"🚫 403 Forbidden for {date} page {page}, attempt {attempt + 1}/{MAX_RETRIES}")
                    
                    # Much longer delays in CI for 403 errors
                    if IS_CI:
                        # In CI: very conservative backoff (30-120 seconds)
                        base_delay = 30 + (attempt * 30) + random.uniform(0, 30)
                        retry_delay = min(base_delay, 120)  # Cap at 2 minutes
                    else:
                        # Local: normal exponential backoff
                        base_delay = RETRY_DELAY * (2 ** attempt) + random.uniform(0, 5)
                        retry_delay = max(5, min(base_delay, 30))  # Clamp between 5-30 seconds
                    
                    logger.info(f"⏳ Rate limited - waiting {retry_delay:.1f} seconds before retry...")
                    await asyncio.sleep(retry_delay)
                    continue
                
                # Other HTTP errors: log and return None
                else:
                    logger.error(f"❌ HTTP {response.status} error for {date} page {page}")
                    # For other 4xx errors in CI, wait longer before giving up
                    if IS_CI and 400 <= response.status < 500 and attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(random.uniform(15, 30))
                        continue
                    return None
                    
        except asyncio.TimeoutError:
            # Handle request timeouts
            logger.error(f"⏰ Request timeout ({REQUEST_TIMEOUT}s) for {date} page {page}, attempt {attempt + 1}/{MAX_RETRIES}")
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (2 if IS_CI else 1)  # Longer delay in CI
                await asyncio.sleep(delay)
                continue
            return None
            
        except Exception as e:
            # Handle any other network or parsing errors
            logger.error(f"💥 Unexpected error fetching {date} page {page}, attempt {attempt + 1}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (2 if IS_CI else 1)  # Longer delay in CI
                await asyncio.sleep(delay)
                continue
            return None
    
    # All retries exhausted
    logger.error(f"🔴 All {MAX_RETRIES} retry attempts failed for {date} page {page}")
    return None


async def fetch_all_pages_for_date(session: aiohttp.ClientSession, date: str, semaphore: asyncio.Semaphore) -> List[Dict[str, Any]]:
    """
    Fetch all paginated events for a specific date using concurrent requests.
    
    The HackTown API returns events in paginated format. This function:
    1. Fetches the first page to determine total page count
    2. Concurrently fetches all remaining pages
    3. Combines all events into a single list
    
    Args:
        session (aiohttp.ClientSession): HTTP session for requests
        date (str): Event date in YYYY-MM-DD format
        semaphore (asyncio.Semaphore): Concurrency limiter to prevent overwhelming the API
        
    Returns:
        List[Dict[str, Any]]: Combined list of all events for the date
        
    Concurrency Strategy:
        - First page is fetched sequentially to get pagination metadata
        - Remaining pages are fetched concurrently with semaphore limiting
        - This balances speed with API respect
    """
    all_events = []

    # ========================================================================
    # STEP 1: Fetch first page to determine pagination
    # ========================================================================
    # The first page contains metadata about total pages available
    # We need this information before we can fetch remaining pages concurrently
    
    async with semaphore:  # Respect concurrency limits even for first page
        logger.info(f"Fetching page 1 for {date} to determine total pages...")
        first_page_data = await fetch_page(session, date, 1)

    # Handle case where first page fails
    if not first_page_data:
        logger.error(f"Failed to fetch first page for {date} - skipping date")
        return []

    # Extract events from first page
    events = first_page_data.get('data', [])
    all_events.extend(events)
    logger.info(f"Page 1 for {date}: {len(events)} events")

    # ========================================================================
    # STEP 2: Determine if additional pages exist
    # ========================================================================
    # Parse pagination metadata from API response
    meta = first_page_data.get('meta', {})
    last_page = meta.get('last_page', 1)
    
    logger.info(f"Date {date} has {last_page} total pages")

    # ========================================================================
    # STEP 3: Fetch remaining pages concurrently (if any)
    # ========================================================================
    if last_page > 1:
        logger.info(f"Fetching pages 2-{last_page} for {date} concurrently...")
        
        # Create async tasks for all remaining pages
        tasks = []
        for page in range(2, last_page + 1):
            # Create a closure to capture the page number correctly
            async def fetch_with_semaphore(p):
                async with semaphore:  # Limit concurrent requests
                    logger.info(f"Fetching page {p}/{last_page} for {date}...")
                    return await fetch_page(session, date, p)

            tasks.append(fetch_with_semaphore(page))

        # Execute all page requests concurrently
        # asyncio.gather maintains order and waits for all tasks
        results = await asyncio.gather(*tasks)

        # ====================================================================
        # STEP 4: Process results and combine events
        # ====================================================================
        successful_pages = 0
        for page_num, result in enumerate(results, start=2):
            if result:
                page_events = result.get('data', [])
                all_events.extend(page_events)
                successful_pages += 1
                logger.info(f"Page {page_num} for {date}: {len(page_events)} events")
            else:
                logger.warning(f"Failed to fetch page {page_num} for {date}")
        
        logger.info(f"Successfully fetched {successful_pages}/{last_page-1} additional pages for {date}")

    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    logger.info(f"Total events collected for {date}: {len(all_events)}")
    return all_events


def process_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process raw event data to add location categorization fields.
    
    This function enhances each event with standardized location information
    that enables filtering and geographical grouping in the web application.
    
    Processing Steps:
    1. Extract the 'place' field from each event
    2. Normalize the location using the normalize_and_locate function
    3. Add 'filterLocation' and 'nearLocation' fields to each event
    
    Args:
        events (List[Dict[str, Any]]): Raw event data from API
        
    Returns:
        List[Dict[str, Any]]: Events enhanced with location categorization
        
    Added Fields:
        - filterLocation: Standardized venue name for precise filtering
        - nearLocation: Broader geographical area for proximity-based grouping
    """
    for event in events:
        # Extract location from event data (may be empty or None)
        place = event.get('place', '')
        
        # Normalize and categorize the location
        filter_location, near_location = normalize_and_locate(place)
        
        # Add the processed location fields to the event
        event['filterLocation'] = filter_location
        event['nearLocation'] = near_location

    return events


def save_events_to_file(date: str, events: List[Dict[str, Any]]):
    """
    Save processed events to a structured JSON file with metadata.
    
    This function creates organized, timestamped JSON files that serve as the
    data source for the web application. Each file contains events for a single
    date along with processing metadata.
    
    File Structure:
    - Filename: hacktown_events_YYYY-MM-DD.json
    - Location: events/ directory
    - Content: Metadata + processed events array
    
    Args:
        date (str): Event date in YYYY-MM-DD format
        events (List[Dict[str, Any]]): Raw events to process and save
        
    File Content Structure:
        {
            "date": "YYYY-MM-DD",
            "total_events": number,
            "scraped_at": "ISO timestamp in BRT",
            "events": [processed_event_objects]
        }
    """
    # ========================================================================
    # DIRECTORY SETUP
    # ========================================================================
    # Ensure the output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ========================================================================
    # EVENT PROCESSING
    # ========================================================================
    # Add location categorization to all events
    processed_events = process_events(events)

    # ========================================================================
    # FILE PATH GENERATION
    # ========================================================================
    # Create standardized filename based on date
    filename = f"hacktown_events_{date}.json"
    filepath = os.path.join(OUTPUT_DIR, filename)

    # ========================================================================
    # TIMESTAMP GENERATION
    # ========================================================================
    # Generate timestamp in Brazilian timezone (BRT/BRST)
    # This ensures timestamps match the local event timezone
    utc_now = datetime.now(ZoneInfo('UTC'))
    brt_now = utc_now.astimezone(ZoneInfo('America/Sao_Paulo'))

    # ========================================================================
    # DATA STRUCTURE PREPARATION
    # ========================================================================
    # Create structured output with metadata and events
    output_data = {
        "date": date,                           # Event date for reference
        "total_events": len(processed_events),  # Quick count for web app
        "scraped_at": brt_now.isoformat(),     # Processing timestamp
        "events": processed_events              # Full event data array
    }

    # ========================================================================
    # FILE WRITING
    # ========================================================================
    # Write JSON with proper encoding and formatting
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(
            output_data, 
            f, 
            ensure_ascii=False,  # Preserve Unicode characters (Portuguese text)
            indent=2             # Pretty-print for readability
        )

    logger.info(f"Successfully saved {len(processed_events)} events to {filepath}")
    logger.info(f"File size: {os.path.getsize(filepath):,} bytes")


async def warm_up_session(session: aiohttp.ClientSession):
    """
    Warm up the session by making a request to the main website first.
    This helps establish a more legitimate browsing pattern.
    """
    try:
        logger.info("🔥 Warming up session by visiting main website...")
        
        # Visit the main website first to establish session
        async with session.get(
            'https://hacktown2025.yazo.app.br/',
            headers=get_headers(),
            timeout=aiohttp.ClientTimeout(total=15)
        ) as response:
            if response.status == 200:
                logger.info("✅ Session warmed up successfully")
                # Wait a bit to simulate human browsing
                await asyncio.sleep(random.uniform(2, 5))
            else:
                logger.warning(f"⚠️ Session warmup returned status {response.status}")
                
    except Exception as e:
        logger.warning(f"⚠️ Session warmup failed: {e}")
        # Continue anyway, warmup is optional


async def fetch_all_dates(dates: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Orchestrate concurrent fetching of events across multiple dates.
    
    This is the main coordination function that manages:
    - HTTP session lifecycle and connection pooling
    - Concurrency control via semaphores
    - Environment-specific optimizations
    - Task scheduling and result aggregation
    
    Args:
        dates (List[str]): List of dates to scrape in YYYY-MM-DD format
        
    Returns:
        Dict[str, List[Dict[str, Any]]]: Mapping of date -> events list
        
    Architecture:
        - Single HTTP session with connection pooling for efficiency
        - Semaphore-controlled concurrency to respect API limits
        - Environment-aware connection settings (CI vs local)
        - Cookie jar for session state management
    """
    all_results = {}

    # ========================================================================
    # CONCURRENCY CONTROL SETUP
    # ========================================================================
    # Create semaphore to limit concurrent requests and prevent API overload
    # The limit is environment-dependent (conservative in CI, normal locally)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    logger.info(f"Using semaphore with {MAX_CONCURRENT_REQUESTS} concurrent requests")

    # ========================================================================
    # HTTP SESSION CONFIGURATION
    # ========================================================================
    # Configure connection pooling based on environment
    # CI environments get very conservative settings to avoid rate limiting
    
    if IS_CI:
        # CI Environment: Ultra-conservative settings
        connector = aiohttp.TCPConnector(
            limit=3,              # Even smaller connection pool
            limit_per_host=1,     # Only 1 connection per host in CI
            ttl_dns_cache=300,    # DNS cache timeout (5 minutes)
            force_close=True,     # Force close connections (no keep-alive)
            enable_cleanup_closed=True  # Clean up closed connections
        )
        logger.info("Using CI-optimized connection settings (ultra-conservative)")
    else:
        # Local Development: Normal settings for better performance
        connector = aiohttp.TCPConnector(
            limit=20,             # Reasonable total connection pool
            limit_per_host=10,    # Allow multiple connections per host
            ttl_dns_cache=300     # DNS cache timeout (5 minutes)
        )
        logger.info("Using local development connection settings (normal)")

    # ========================================================================
    # SESSION LIFECYCLE MANAGEMENT
    # ========================================================================
    # Create HTTP session with:
    # - Connection pooling for efficiency
    # - Cookie jar for session state (if API requires it)
    # - Automatic resource cleanup via context manager
    
    # Enhanced timeout settings for CI
    timeout = aiohttp.ClientTimeout(
        total=60 if IS_CI else 30,      # Longer total timeout in CI
        connect=30 if IS_CI else 10,    # Longer connect timeout in CI
        sock_read=30 if IS_CI else 10   # Longer read timeout in CI
    )
    
    async with aiohttp.ClientSession(
        connector=connector,
        cookie_jar=aiohttp.CookieJar(),  # Maintain cookies across requests
        timeout=timeout
    ) as session:
        
        logger.info(f"Created HTTP session - starting to fetch {len(dates)} dates")
        
        # ====================================================================
        # SESSION WARMING (CI ONLY)
        # ====================================================================
        # In CI, warm up the session to appear more like a real browser
        if IS_CI:
            await warm_up_session(session)
        
        # ====================================================================
        # TASK CREATION AND SCHEDULING
        # ====================================================================
        # Create async tasks for each date
        # Each task will handle all pages for its assigned date
        
        tasks = []
        for date in dates:
            logger.info(f"Scheduling task for date: {date}")
            task = fetch_all_pages_for_date(session, date, semaphore)
            tasks.append(task)

        # ====================================================================
        # CONCURRENT EXECUTION
        # ====================================================================
        # Execute all date-fetching tasks concurrently
        # asyncio.gather waits for all tasks and preserves order
        
        logger.info("Starting concurrent execution of all date tasks...")
        start_time = time.time()
        
        results = await asyncio.gather(*tasks)
        
        execution_time = time.time() - start_time
        logger.info(f"All date tasks completed in {execution_time:.2f} seconds")

        # ====================================================================
        # RESULT AGGREGATION
        # ====================================================================
        # Map results back to their corresponding dates
        # This creates the final date -> events mapping
        
        for date, events in zip(dates, results):
            all_results[date] = events
            event_count = len(events) if events else 0
            logger.info(f"Date {date}: {event_count} events collected")

    # Session automatically closed here due to context manager
    logger.info("HTTP session closed - all network operations complete")
    return all_results


async def main():
    """
    Main orchestration function for the HackTown 2025 event scraping process.
    
    This function coordinates the entire scraping workflow:
    1. Initialize logging and load existing data
    2. Execute concurrent event fetching across all dates
    3. Process and save individual date files
    4. Generate summary statistics and metadata
    5. Handle failure scenarios gracefully
    
    Workflow Architecture:
    - Fault-tolerant: Preserves existing data if scraping fails
    - Incremental: Updates only successfully scraped data
    - Monitored: Comprehensive logging and performance metrics
    - Resilient: Handles partial failures gracefully
    
    Output Files:
        - hacktown_events_YYYY-MM-DD.json: Daily event data
        - summary.json: Overall statistics and metadata
        - locations.json: Location mapping data (if applicable)
    """
    # ========================================================================
    # INITIALIZATION AND STARTUP
    # ========================================================================
    logger.info("=" * 60)
    logger.info("🚀 Starting HackTown 2025 Event Scraper (Async Version)")
    logger.info("=" * 60)
    logger.info(f"Environment: {'CI/CD' if IS_CI else 'Local Development'}")
    logger.info(f"Dates to scrape: {', '.join(EVENT_DATES)}")
    logger.info(f"Max concurrent requests: {MAX_CONCURRENT_REQUESTS}")
    logger.info(f"Output directory: {os.path.abspath(OUTPUT_DIR)}")

    # Start performance timing
    start_time = time.time()

    # ========================================================================
    # EXISTING DATA RECOVERY
    # ========================================================================
    # Load existing summary to preserve data in case of scraping failure
    # This ensures we don't lose previously successful scraping results
    
    summary_file = os.path.join(OUTPUT_DIR, "summary.json")
    existing_summary = {}
    
    if os.path.exists(summary_file):
        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                existing_summary = json.load(f)
            logger.info(f"📊 Loaded existing summary: {existing_summary.get('total_events', 0)} events from previous run")
            logger.info(f"📅 Last successful scrape: {existing_summary.get('scraping_completed', 'Unknown')}")
        except Exception as e:
            logger.warning(f"⚠️  Could not load existing summary: {e}")
            logger.info("Proceeding with fresh scraping session")
    else:
        logger.info("📝 No existing summary found - this appears to be the first run")

    # ========================================================================
    # MAIN SCRAPING EXECUTION
    # ========================================================================
    logger.info("\n" + "🌐 Starting concurrent event fetching...")
    logger.info("-" * 50)
    
    # Execute the main scraping workflow
    all_events = await fetch_all_dates(EVENT_DATES)

    # ========================================================================
    # RESULTS PROCESSING AND FILE GENERATION
    # ========================================================================
    logger.info("\n" + "💾 Processing results and saving files...")
    logger.info("-" * 50)
    
    # Track overall statistics
    total_events = 0
    successful_dates = 0
    failed_dates = []
    
    # Process each date's results
    for date, events in all_events.items():
        if events:
            # Success case: save events and update counters
            save_events_to_file(date, events)
            total_events += len(events)
            successful_dates += 1
            logger.info(f"✅ {date}: {len(events)} events saved successfully")
        else:
            # Failure case: log and track for summary
            failed_dates.append(date)
            logger.warning(f"❌ {date}: No events retrieved (scraping failed)")

    # ========================================================================
    # PERFORMANCE METRICS AND SUMMARY
    # ========================================================================
    elapsed_time = time.time() - start_time
    
    logger.info("\n" + "=" * 60)
    logger.info("📈 SCRAPING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"✅ Successful dates: {successful_dates}/{len(EVENT_DATES)}")
    logger.info(f"📊 Total events scraped: {total_events:,}")
    logger.info(f"⏱️  Total execution time: {elapsed_time:.2f} seconds")
    logger.info(f"🚀 Average speed: {total_events/elapsed_time:.1f} events/second" if elapsed_time > 0 else "🚀 Speed: N/A")
    logger.info(f"💾 Output directory: {os.path.abspath(OUTPUT_DIR)}")
    
    if failed_dates:
        logger.warning(f"⚠️  Failed dates: {', '.join(failed_dates)}")
    
    # Location cache efficiency metrics
    logger.info(f"🗺️  Location cache: {len(location_cache)} unique locations processed")

    # ========================================================================
    # SUMMARY FILE GENERATION
    # ========================================================================
    # Generate timestamp in Brazilian timezone for consistency
    utc_now = datetime.now(ZoneInfo('UTC'))
    brt_now = utc_now.astimezone(ZoneInfo('America/Sao_Paulo'))

    # Determine if this scraping session was successful
    fetch_successful = successful_dates > 0
    
    if fetch_successful:
        # Success case: Update summary with new data
        summary_data = {
            "scraping_completed": brt_now.isoformat(),
            "total_events": total_events,
            "successful_dates": successful_dates,
            "failed_dates": failed_dates,
            "dates_processed": EVENT_DATES,
            "files_created": [f"hacktown_events_{date}.json" for date in EVENT_DATES if date not in failed_dates],
            "scraping_time_seconds": round(elapsed_time, 2),
            "events_per_second": round(total_events/elapsed_time, 2) if elapsed_time > 0 else 0,
            "location_cache_size": len(location_cache)
        }
        logger.info("✅ Scraping successful - updating summary with new data")
        
    else:
        # Failure case: Preserve existing data and log failure
        summary_data = {
            "scraping_completed": existing_summary.get("scraping_completed", "Never"),
            "total_events": existing_summary.get("total_events", 0),
            "successful_dates": existing_summary.get("successful_dates", 0),
            "failed_dates": failed_dates,
            "dates_processed": EVENT_DATES,
            "files_created": existing_summary.get("files_created", []),
            "scraping_time_seconds": round(elapsed_time, 2),
            "last_failed_attempt": brt_now.isoformat(),
            "consecutive_failures": existing_summary.get("consecutive_failures", 0) + 1
        }
        logger.error("❌ Scraping failed completely - preserving existing summary data")

    # Save summary file
    try:
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
        logger.info(f"📋 Summary saved to: {summary_file}")
    except Exception as e:
        logger.error(f"❌ Failed to save summary file: {e}")

    # ========================================================================
    # FINAL STATUS AND CLEANUP
    # ========================================================================
    logger.info("\n" + "🏁 Scraping process completed!")
    
    if fetch_successful:
        logger.info("✅ Status: SUCCESS")
        logger.info("🎉 Event data is ready for the web application")
    else:
        logger.error("❌ Status: FAILED")
        logger.error("🔧 Check logs above for error details and retry")
    
    logger.info("=" * 60)

# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """
    Script entry point - executes the main scraping workflow.
    
    This section runs when the script is executed directly (not imported).
    It uses asyncio.run() to execute the async main() function, which handles
    all the event loop management automatically.
    
    Usage:
        python scrape_hacktown.py
        
    The script will:
    1. Create the events/ directory if it doesn't exist
    2. Scrape all HackTown 2025 events across configured dates
    3. Save individual JSON files for each date
    4. Generate a summary.json with overall statistics
    5. Log comprehensive progress and performance metrics
    
    Exit Codes:
        0: Success (events scraped and saved)
        1: Failure (check logs for details)
    """
    try:
        # Execute the main async workflow
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print("\n🛑 Scraping interrupted by user (Ctrl+C)")
        print("📝 Partial results may have been saved to the events/ directory")
        exit(1)
    except Exception as e:
        # Handle any unexpected errors
        print(f"\n💥 Unexpected error occurred: {e}")
        print("🔧 Check the logs above for detailed error information")
        exit(1)
