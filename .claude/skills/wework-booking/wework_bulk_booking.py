#!/usr/bin/env python3
"""
WeWork Bulk Desk Booking Script
Books hot desks for multiple consecutive days at {{WEWORK_LOCATION}}.

Usage:
    # Dry run (default)
    python wework_bulk_booking.py --start 2026-01-24 --days 30

    # Live run with confirmation
    python wework_bulk_booking.py --start 2026-01-24 --days 30 --live

    # Weekdays only
    python wework_bulk_booking.py --start 2026-01-24 --days 30 --live --weekdays-only

    # Resume from a specific date (skips already-booked dates)
    python wework_bulk_booking.py --start 2026-01-24 --days 30 --live --resume

Environment Variables:
    WEWORK_AUTH_TOKEN: JWT auth token (required for live runs)
    WEWORK_COOKIES: JSON string of cookies (optional, will use defaults)
"""

import os
import sys
import logging
import base64
import time
import requests
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
import json as json_module

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

BASE_URL = "https://members.wework.com/workplaceone/api/common-booking/"

# Location identifiers for {{WEWORK_LOCATION}} — replace with your location's IDs
LOCATION_ID = "{{WEWORK_LOCATION_ID}}"
SPACE_ID = "{{WEWORK_SPACE_ID_NUM}}"
WEWORK_SPACE_ID = "{{WEWORK_SPACE_UUID}}"
WEWORK_UUID = "{{WEWORK_USER_UUID}}"

# Booking type constants (from WeWork API)
SPACE_TYPE_HOT_DESK = 4       # Hot desk booking
LOCATION_TYPE_BUILDING = 2    # Building location
CREDIT_RATIO_DEFAULT = 25     # Credits per booking (0 for unlimited plans)

# Rate limiting config
MIN_DELAY_SECONDS = 3
MAX_DELAY_SECONDS = 8
RETRY_DELAY_SECONDS = 30
MAX_RETRIES = 3

# State file for resume capability
STATE_FILE = Path(__file__).parent.parent.parent.parent / "active" / "wework_booking_state.json"

# Default cookies (Cloudflare protection + session)
DEFAULT_COOKIES = {
    "DeviceId": "{{WEWORK_DEVICE_ID}}",
    "CurrentUserName": "your-personal-email@example.com",
    "_legacy_auth0.{{WEWORK_AUTH0_KEY}}.is.authenticated": "true",
    "auth0.{{WEWORK_AUTH0_KEY}}.is.authenticated": "true",
}


# ============================================================================
# Token Management
# ============================================================================

def get_auth_token() -> str:
    """Load auth token from environment variable."""
    token = os.environ.get("WEWORK_AUTH_TOKEN", "").strip()
    if not token:
        logger.error("WEWORK_AUTH_TOKEN environment variable not set")
        logger.info("Export your token: export WEWORK_AUTH_TOKEN='eyJ...'")
        sys.exit(1)
    return token


def decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without verification (for reading claims only)."""
    try:
        payload = token.split('.')[1]
        # Add padding if needed
        payload += '=' * (4 - len(payload) % 4)
        return json_module.loads(base64.urlsafe_b64decode(payload))
    except Exception as e:
        logger.warning(f"Could not decode JWT: {e}")
        return {}


def check_token_expiry(token: str) -> bool:
    """
    Check if token is expired or expiring soon.
    Returns True if token is valid, False if expired/expiring.
    """
    payload = decode_jwt_payload(token)
    if not payload:
        logger.warning("Could not verify token expiry - proceeding anyway")
        return True

    exp_timestamp = payload.get("exp")
    if not exp_timestamp:
        return True

    exp_time = datetime.utcfromtimestamp(exp_timestamp)
    now = datetime.utcnow()
    time_remaining = exp_time - now

    if time_remaining.total_seconds() <= 0:
        logger.error(f"Token EXPIRED at {exp_time.isoformat()} UTC")
        return False

    if time_remaining.total_seconds() < 3600:  # Less than 1 hour
        logger.warning(f"Token expires in {time_remaining} - consider refreshing")

    logger.info(f"Token valid until {exp_time.isoformat()} UTC ({time_remaining} remaining)")
    return True


def get_cookies() -> dict:
    """Load cookies from environment or use defaults."""
    cookies_json = os.environ.get("WEWORK_COOKIES", "")
    if cookies_json:
        try:
            return json_module.loads(cookies_json)
        except json_module.JSONDecodeError:
            logger.warning("Invalid WEWORK_COOKIES JSON, using defaults")
    return DEFAULT_COOKIES.copy()


# ============================================================================
# State Management (Resume Capability)
# ============================================================================

def load_state() -> dict:
    """Load booking state from file."""
    if STATE_FILE.exists():
        try:
            return json_module.loads(STATE_FILE.read_text())
        except Exception as e:
            logger.warning(f"Could not load state file: {e}")
    return {"completed": [], "failed": []}


def save_state(state: dict) -> None:
    """Save booking state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json_module.dumps(state, indent=2))


def clear_state() -> None:
    """Clear the state file."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()


# ============================================================================
# Date Formatting
# ============================================================================

def get_ordinal_suffix(day: int) -> str:
    """Return ordinal suffix for a day number (1st, 2nd, 3rd, etc.)"""
    if 11 <= day <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def format_day(date: datetime) -> str:
    """Format date as 'Friday, January 23rd'"""
    day = date.day
    suffix = get_ordinal_suffix(day)
    return date.strftime(f"%A, %B {day}{suffix}")


def get_utc_offset(date: datetime) -> tuple[str, int]:
    """
    Get UTC offset for your location on a given date.
    Returns (offset_string, hours_offset) e.g. ("-07:00", -7) or ("-06:00", -6)

    Update DST logic below to match your timezone. Example (Mountain Time):
    - MST (Mountain Standard Time): UTC-7 (Nov - Mar)
    - MDT (Mountain Daylight Time): UTC-6 (Mar - Nov)
    """
    # DST in Canada: 2nd Sunday of March to 1st Sunday of November
    year = date.year

    # Find 2nd Sunday of March
    march_1 = datetime(year, 3, 1)
    days_until_sunday = (6 - march_1.weekday()) % 7
    dst_start = march_1 + timedelta(days=days_until_sunday + 7)  # 2nd Sunday

    # Find 1st Sunday of November
    nov_1 = datetime(year, 11, 1)
    days_until_sunday = (6 - nov_1.weekday()) % 7
    dst_end = nov_1 + timedelta(days=days_until_sunday)  # 1st Sunday

    if dst_start <= date.replace(hour=0, minute=0, second=0, microsecond=0) < dst_end:
        return ("-06:00", -6)  # MDT
    return ("-07:00", -7)  # MST


# ============================================================================
# Payload Building
# ============================================================================

def build_booking_payload(date: datetime) -> dict:
    """Build the booking request payload for a specific date."""

    utc_offset_str, utc_offset_hours = get_utc_offset(date)

    # Local times (Mountain Time)
    start_local = date.strftime("%Y-%m-%d") + " 06:00"
    end_local = date.strftime("%Y-%m-%d") + " 23:59"

    # UTC times
    # 6:00 AM MT = 6:00 + abs(offset) hours UTC
    start_utc_hour = 6 + abs(utc_offset_hours)
    start_utc = date.strftime(f"%Y-%m-%dT{start_utc_hour:02d}:00:00Z")

    # 23:59 PM MT = next day at (23:59 + abs(offset)) - 24 hours UTC
    end_utc_hour = (23 + abs(utc_offset_hours)) % 24
    end_date = date + timedelta(days=1) if (23 + abs(utc_offset_hours)) >= 24 else date
    end_utc = end_date.strftime(f"%Y-%m-%dT{end_utc_hour:02d}:59:00Z")

    day_formatted = format_day(date)

    return {
        "ApplicationType": "WorkplaceOne",
        "PlatformType": "WEB",
        "SpaceType": SPACE_TYPE_HOT_DESK,
        "ReservationID": "",
        "TriggerCalendarEvent": True,
        "Notes": {
            "locationAddress": "{{WEWORK_ADDRESS}}",
            "locationCity": "{{WEWORK_CITY}}",
            "locationState": "{{WEWORK_STATE}}",
            "locationCountry": "{{WEWORK_COUNTRY}}",
            "locationName": "{{WEWORK_LOCATION}}"
        },
        "MailData": {
            "dayFormatted": day_formatted,
            "startTimeFormatted": "06:00 AM",
            "endTimeFormatted": "11:59 PM",  # Fixed: was "23:59 PM" which is redundant
            "locationAddress": "{{WEWORK_ADDRESS}}",
            "creditsUsed": "0",
            "Capacity": "1",
            "TimezoneUsed": f"GMT {utc_offset_str[:3]}:00",
            "TimezoneIana": "{{WEWORK_TIMEZONE_IANA}}",  # Your location's IANA timezone
            "TimezoneWin": "{{WEWORK_TIMEZONE_WIN}}",
            "startDateTime": start_local,
            "endDateTime": end_local,
            "locationName": "{{WEWORK_LOCATION}}",
            "locationCity": "{{WEWORK_CITY}}",
            "locationCountry": "{{WEWORK_COUNTRY}}",
            "locationState": "{{WEWORK_STATE}}"
        },
        "LocationType": LOCATION_TYPE_BUILDING,
        "UTCOffset": utc_offset_str,
        "CreditRatio": CREDIT_RATIO_DEFAULT,
        "LocationID": LOCATION_ID,
        "SpaceID": SPACE_ID,
        "WeWorkSpaceID": WEWORK_SPACE_ID,
        "StartTime": start_utc,
        "EndTime": end_utc
    }


# ============================================================================
# HTTP Session & Requests
# ============================================================================

def create_session(auth_token: str, cookies: dict) -> requests.Session:
    """Create a configured requests session with connection pooling."""
    session = requests.Session()

    session.headers.update({
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "authorization": f"Bearer {auth_token}",
        "content-type": "application/json",
        "fe-pg": "/workplaceone/content2/bookings/desks",
        "origin": "https://members.wework.com",
        "referer": "https://members.wework.com/workplaceone/content2/bookings/desks",
        "request-source": "MemberWeb/WorkplaceOne/Prod",
        "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36",
        "weworkmembertype": "2",
        "weworkuuid": WEWORK_UUID
    })

    session.cookies.update(cookies)

    return session


def book_desk(session: requests.Session, date: datetime, dry_run: bool = True) -> dict:
    """
    Book a desk for a specific date.

    Args:
        session: Configured requests session
        date: The date to book
        dry_run: If True, just print what would be done without making the request

    Returns:
        dict with 'success' boolean and 'message' or 'error'
    """
    payload = build_booking_payload(date)
    date_str = date.strftime("%Y-%m-%d")

    if dry_run:
        logger.info(f"[DRY RUN] Would book: {format_day(date)} ({date_str})")
        logger.debug(f"  StartTime: {payload['StartTime']}, EndTime: {payload['EndTime']}")
        return {"success": True, "message": "Dry run - no request made"}

    import random

    for attempt in range(MAX_RETRIES):
        try:
            response = session.post(BASE_URL, json=payload, timeout=30)

            # Success: 200 OK or 201 Created
            if response.status_code in (200, 201):
                logger.info(f"✓ Booked: {format_day(date)} ({date_str})")
                try:
                    response_data = response.json()
                except (json_module.JSONDecodeError, ValueError):
                    response_data = {"raw": response.text[:500]}
                return {"success": True, "message": "Booked successfully", "response": response_data}

            # Rate limited
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", RETRY_DELAY_SECONDS))
                logger.warning(f"Rate limited on {date_str}, waiting {retry_after}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(retry_after)
                continue

            # Auth expired
            elif response.status_code == 401:
                logger.error("Auth token expired - please refresh your token")
                return {"success": False, "error": "Auth token expired", "status": 401}

            # Forbidden (likely Cloudflare)
            elif response.status_code == 403:
                logger.error(f"Forbidden (403) - Cloudflare may be blocking. Response: {response.text[:200]}")
                return {"success": False, "error": "Forbidden - possible Cloudflare block", "status": 403}

            # Conflict (already booked?)
            elif response.status_code == 409:
                logger.warning(f"Conflict on {date_str} - may already be booked")
                return {"success": False, "error": "Conflict - possibly already booked", "status": 409}

            # Other errors
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(f"Failed {date_str}: {error_msg}")
                return {"success": False, "error": error_msg, "status": response.status_code}

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on {date_str} (attempt {attempt + 1}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            return {"success": False, "error": "Request timed out after retries"}

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error on {date_str}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            return {"success": False, "error": str(e)}

    return {"success": False, "error": "Max retries exceeded"}


# ============================================================================
# Main Booking Logic
# ============================================================================

def book_multiple_days(
    start_date: datetime,
    num_days: int = 30,
    dry_run: bool = True,
    weekdays_only: bool = False,
    resume: bool = False
) -> dict:
    """
    Book desks for multiple consecutive days.

    Args:
        start_date: First date to book
        num_days: Number of days to book
        dry_run: If True, just print what would be done
        weekdays_only: If True, skip Saturday (5) and Sunday (6)
        resume: If True, skip dates already in state file

    Returns:
        Summary dict with successes/failures
    """
    import random

    # Load state for resume capability
    state = load_state() if resume else {"completed": [], "failed": []}
    completed_dates = set(state.get("completed", []))

    results = {"success": [], "failed": []}

    # Build list of dates to book
    dates_to_book = []
    for i in range(num_days):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")

        # Skip weekends if requested
        if weekdays_only and current_date.weekday() >= 5:
            logger.debug(f"Skipping weekend: {date_str}")
            continue

        # Skip already completed dates if resuming
        if resume and date_str in completed_dates:
            logger.info(f"Skipping (already booked): {date_str}")
            results["success"].append(date_str)
            continue

        dates_to_book.append(current_date)

    if not dates_to_book:
        logger.info("No dates to book!")
        return results

    # Print summary
    logger.info("=" * 60)
    logger.info(f"WeWork Bulk Booking")
    logger.info(f"  Dates: {dates_to_book[0].strftime('%Y-%m-%d')} to {dates_to_book[-1].strftime('%Y-%m-%d')}")
    logger.info(f"  Total bookings: {len(dates_to_book)}")
    logger.info(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info(f"  Weekdays only: {weekdays_only}")
    logger.info(f"  Resume mode: {resume}")
    logger.info("=" * 60)

    # Create session (only needed for live runs)
    session = None
    if not dry_run:
        auth_token = get_auth_token()
        if not check_token_expiry(auth_token):
            logger.error("Aborting due to expired token")
            return results
        cookies = get_cookies()
        session = create_session(auth_token, cookies)

    # Book each date
    for i, current_date in enumerate(dates_to_book):
        date_str = current_date.strftime("%Y-%m-%d")

        result = book_desk(session, current_date, dry_run=dry_run)

        if result["success"]:
            results["success"].append(date_str)
            state["completed"].append(date_str)
        else:
            results["failed"].append({
                "date": date_str,
                "error": result.get("error", "Unknown error")
            })
            state["failed"].append({
                "date": date_str,
                "error": result.get("error", "Unknown error"),
                "timestamp": datetime.utcnow().isoformat()
            })

            # Stop on auth errors or Cloudflare blocks
            if result.get("status") in (401, 403):
                logger.error("Stopping due to auth/access error")
                break

        # Save state after each booking (for resume capability)
        if not dry_run:
            save_state(state)

        # Random delay between requests (skip on dry run and last item)
        if not dry_run and i < len(dates_to_book) - 1:
            delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
            logger.debug(f"Waiting {delay:.1f}s before next request...")
            time.sleep(delay)

    # Summary
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Successful: {len(results['success'])}")
    logger.info(f"Failed: {len(results['failed'])}")

    if results["failed"]:
        logger.warning("Failed bookings:")
        for fail in results["failed"]:
            logger.warning(f"  - {fail['date']}: {fail['error']}")

    # Save final results
    if not dry_run:
        results_file = STATE_FILE.parent / f"wework_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        results_file.write_text(json_module.dumps(results, indent=2))
        logger.info(f"Results saved to: {results_file}")

    return results


def confirm_live_run(dates_count: int) -> bool:
    """Ask user to confirm before making live requests."""
    print(f"\n⚠️  You are about to make {dates_count} LIVE booking requests to WeWork.")
    print("This will create actual reservations on your account.\n")
    response = input("Type 'yes' to proceed: ").strip().lower()
    return response == "yes"


# ============================================================================
# CLI Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Book WeWork desks in bulk",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --start 2026-01-24 --days 30              # Dry run
  %(prog)s --start 2026-01-24 --days 30 --live       # Live run
  %(prog)s --start 2026-01-24 --days 30 --live --weekdays-only
  %(prog)s --live --resume                           # Resume interrupted run

Environment variables:
  WEWORK_AUTH_TOKEN   JWT auth token (required for live runs)
  WEWORK_COOKIES      JSON string of cookies (optional)
        """
    )
    parser.add_argument(
        "--start", type=str, default="2026-01-24",
        help="Start date (YYYY-MM-DD), default: 2026-01-24"
    )
    parser.add_argument(
        "--days", type=int, default=30,
        help="Number of days to book, default: 30"
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Actually make requests (default is dry-run)"
    )
    parser.add_argument(
        "--weekdays-only", action="store_true",
        help="Skip weekends (Saturday and Sunday)"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from last run, skipping already-booked dates"
    )
    parser.add_argument(
        "--clear-state", action="store_true",
        help="Clear the state file and start fresh"
    )
    parser.add_argument(
        "--no-confirm", action="store_true",
        help="Skip confirmation prompt for live runs"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose/debug logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.clear_state:
        clear_state()
        logger.info("State file cleared")
        sys.exit(0)

    start = datetime.strptime(args.start, "%Y-%m-%d")

    # Confirmation for live runs
    if args.live and not args.no_confirm:
        if not confirm_live_run(args.days):
            logger.info("Aborted by user")
            sys.exit(0)

    book_multiple_days(
        start,
        num_days=args.days,
        dry_run=not args.live,
        weekdays_only=args.weekdays_only,
        resume=args.resume
    )
