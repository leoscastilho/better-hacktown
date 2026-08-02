#!/usr/bin/env python3
"""
Yazo provider (HackTown 2025).

The 2025 schedule came from the Yazo API (hacktown-2025-ss-v2.api.yazo.com.br),
served paginated per day. This module keeps that exact fetch logic. It returns
the raw event dicts unchanged; sync_common adds filterLocation/nearLocation and
writes them out, so the 2025 output stays byte-compatible with what shipped.

Connection details come from config/years.json -> years.2025.api.

License: MIT
"""

import os
import time
import random
import asyncio
import logging
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-year API config (set by configure() from config/years.json).
# ---------------------------------------------------------------------------
BASE_URL = ""
API_CATEGORY_ID = "42"
API_PRODUCT_IDS = "[2]"
API_PRODUCT_IDENTIFIER = "1"
API_ORIGIN = "https://hacktown2025.yazo.app.br"
API_REFERER = "https://hacktown2025.yazo.app.br/"


def configure(api_config):
    """Load the year's Yazo API settings (endpoint + params + headers)."""
    global BASE_URL, API_CATEGORY_ID, API_PRODUCT_IDS
    global API_PRODUCT_IDENTIFIER, API_ORIGIN, API_REFERER
    api_config = api_config or {}
    BASE_URL = api_config.get("base_url", "")
    API_CATEGORY_ID = str(api_config.get("category_id", "42"))
    API_PRODUCT_IDS = str(api_config.get("product_ids", "[2]"))
    API_PRODUCT_IDENTIFIER = str(api_config.get("product_identifier", "1"))
    API_ORIGIN = api_config.get("origin", "")
    API_REFERER = api_config.get("referer", "")


# ---------------------------------------------------------------------------
# Environment-adaptive rate limiting (conservative in CI, normal locally).
# FORCE_LOCAL_MODE=true (Docker) opts out of the CI throttling.
# ---------------------------------------------------------------------------
FORCE_LOCAL_MODE = os.environ.get('FORCE_LOCAL_MODE', 'false').lower() == 'true'
IS_CI = (os.environ.get('CI', 'false').lower() == 'true'
         or os.environ.get('GITHUB_ACTIONS', 'false').lower() == 'true') and not FORCE_LOCAL_MODE

if IS_CI:
    MAX_CONCURRENT_REQUESTS = 1
    RETRY_DELAY = 20
    MAX_RETRIES = 3
    REQUEST_TIMEOUT = 60
else:
    MAX_CONCURRENT_REQUESTS = 2
    RETRY_DELAY = 5
    MAX_RETRIES = 5
    REQUEST_TIMEOUT = 30


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
        'origin': API_ORIGIN,
        'pragma': 'no-cache',
        'product-identifier': API_PRODUCT_IDENTIFIER,
        'referer': API_REFERER,
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'cross-site',
        'user-agent': random.choice(user_agents),
        'x-requested-with': 'XMLHttpRequest'
    }


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
        'category_id': API_CATEGORY_ID,    # HackTown category identifier (per-year)
        'tag_ids': '[]',                   # No tag filtering (empty array)
        'day[]': [date, '00:00:00.000Z'],  # Date filter with timezone
        'page': str(page),                 # Current page number
        'search': '',                      # No search query
        'product_ids': API_PRODUCT_IDS     # Product identifier(s) (per-year)
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



async def fetch(dates: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Provider entrypoint: fetch all events for the given dates (raw dicts)."""
    return await fetch_all_dates(dates)
