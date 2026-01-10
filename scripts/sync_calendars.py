#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Manual Calendar Editor - Synchronization Script - Fase 3.1 FIXED
Combines stable version with Fase 3 features
Correctly generates both import_calendar.ics and master_calendar.ics
with automatic prep times (TP Antes/TP Depois)

Version: 3.1
Date: January 8, 2026
Developer: PBRANDÃO + AI
"""

import os
import sys
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Dict, Optional, Set

try:
    from icalendar import Calendar, Event
    import requests
    from dotenv import load_dotenv
    import pytz
except ImportError as e:
    print(f"ERRO de importacao: {e}")
    print("Execute: pip install icalendar requests python-dotenv pytz")
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================

load_dotenv()

# Configuration
REPO_PATH = os.getenv('REPO_PATH', '.')
AIRBNB_ICAL_URL = os.getenv('AIRBNB_ICAL_URL', '')
BOOKING_ICAL_URL = os.getenv('BOOKING_ICAL_URL', '')
VRBO_ICAL_URL = os.getenv('VRBO_ICAL_URL', '')
BUFFER_DAYS_BEFORE = int(os.getenv('BUFFER_DAYS_BEFORE', 1))
BUFFER_DAYS_AFTER = int(os.getenv('BUFFER_DAYS_AFTER', 1))

# File paths
IMPORT_CALENDAR_PATH = os.path.join(REPO_PATH, 'import_calendar.ics')
MASTER_CALENDAR_PATH = os.path.join(REPO_PATH, 'master_calendar.ics')
MANUAL_CALENDAR_PATH = os.path.join(REPO_PATH, 'manual_calendar.ics')

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(REPO_PATH, 'sync.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def to_datetime(dt_obj) -> Optional[datetime]:
    """Converte date ou datetime para datetime"""
    if dt_obj is None:
        return None
    if isinstance(dt_obj, datetime):
        if dt_obj.tzinfo is None:
            return dt_obj.replace(tzinfo=pytz.UTC)
        return dt_obj
    elif isinstance(dt_obj, date):
        return datetime.combine(dt_obj, datetime.min.time()).replace(tzinfo=pytz.UTC)
    return None

def to_date(dt_obj) -> Optional[date]:
    """Extrai data de date ou datetime"""
    if dt_obj is None:
        return None
    if isinstance(dt_obj, datetime):
        return dt_obj.date()
    elif isinstance(dt_obj, date):
        return dt_obj
    return None

def normalize_uid(uid: str) -> str:
    """Normaliza UID para comparação"""
    if not uid:
        return ""
    return str(uid).strip().lower()

def log_info(msg):
    """Log info"""
    logger.info(msg)
    print(f"[INFO] {msg}")

def log_warning(msg):
    """Log warning"""
    logger.warning(msg)
    print(f"[WARNING] {msg}")

def log_error(msg):
    """Log error"""
    logger.error(msg)
    print(f"[ERROR] {msg}")

def log_success(msg):
    """Log success"""
    logger.info(msg)
    print(f"[SUCCESS] ✅ {msg}")

# ============================================================================
# DOWNLOAD & IMPORT
# ============================================================================

def download_calendar(url: str, source: str) -> Optional[Calendar]:
    """Download calendar from URL"""
    try:
        if not url:
            log_warning(f"No URL configured for {source}")
            return None

        log_info(f"[IMPORT] Downloading {source}...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        cal = Calendar.from_ical(response.content)
        
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        log_success(f"Downloaded {len(events)} events from {source}")
        
        return cal

    except Exception as e:
        log_error(f"Error downloading {source}: {str(e)}")
        return None

def fetch_all_calendars() -> Optional[Dict[str, Optional[Calendar]]]:
    """Download all 3 calendars"""
    log_info("STEP 1: Importing calendars...")
    
    calendars = {
        'AIRBNB': download_calendar(AIRBNB_ICAL_URL, 'AIRBNB'),
        'BOOKING': download_calendar(BOOKING_ICAL_URL, 'BOOKING'),
        'VRBO': download_calendar(VRBO_ICAL_URL, 'VRBO'),
    }
    
    if all(v is None for v in calendars.values()):
        log_error("[ERRO] Nenhum calendario foi importado com sucesso")
        return None
    
    return calendars

# ============================================================================
# EXTRACT & PROCESS EVENTS
# ============================================================================

def extract_events(calendars: Dict[str, Optional[Calendar]]) -> List[Dict]:
    """Extract events from all calendars"""
    log_info("STEP 2: Extracting events...")
    
    all_events = []
    
    for source, cal in calendars.items():
        if cal is None:
            continue
        
        try:
            for component in cal.walk():
                if component.name == "VEVENT":
                    dtstart = component.get('DTSTART')
                    dtend = component.get('DTEND')
                    
                    event = {
                        'source': source,
                        'uid': str(component.get('UID', '')),
                        'summary': str(component.get('SUMMARY', 'Sem titulo')),
                        'dtstart': dtstart.dt if dtstart else None,
                        'dtend': dtend.dt if dtend else None,
                        'description': str(component.get('DESCRIPTION', '')),
                        'location': str(component.get('LOCATION', '')),
                        'component': component,
                    }
                    
                    all_events.append(event)
        
        except Exception as e:
            log_error(f"Error extracting from {source}: {str(e)}")
            continue
    
    log_info(f"Extracted {len(all_events)} events total")
    return all_events

def deduplicate_events(events: List[Dict]) -> List[Dict]:
    """Remove duplicate events"""
    log_info("STEP 3: Deduplicating events...")
    
    if not events:
        log_warning("No events to deduplicate")
        return []
    
    groups = {}
    
    for event in events:
        key = (
            to_date(event['dtstart']),
            to_date(event['dtend']),
            event['summary']
        )
        
        if key not in groups:
            groups[key] = []
        groups[key].append(event)
    
    deduplicated = []
    for key, group in groups.items():
        best = max(group, key=lambda e: len(e.get('description', '')))
        deduplicated.append(best)
    
    removed = len(events) - len(deduplicated)
    if removed > 0:
        log_warning(f"Removed {removed} duplicates")
    
    return deduplicated

# ============================================================================
# MANUAL CALENDAR HANDLING
# ============================================================================

def load_manual_calendar() -> Optional[Calendar]:
    """Load manual calendar"""
    try:
        if not Path(MANUAL_CALENDAR_PATH).exists():
            log_info(f"No {MANUAL_CALENDAR_PATH} found")
            return None
        
        with open(MANUAL_CALENDAR_PATH, 'rb') as f:
            cal = Calendar.from_ical(f.read())
            log_info(f"Loaded {MANUAL_CALENDAR_PATH}")
            return cal
    
    except Exception as e:
        log_error(f"Error loading manual calendar: {str(e)}")
        return None

def get_blocked_uids(manual_calendar: Optional[Calendar]) -> Set[str]:
    """Extract UIDs marked as PRIVATE (manual blocks)"""
    blocked_uids = set()
    
    if not manual_calendar:
        return blocked_uids
    
    try:
        for component in manual_calendar.walk():
            if component.name == "VEVENT":
                event_class = component.get('CLASS')
                if event_class and str(event_class).lower() == 'private':
                    uid = normalize_uid(str(component.get('UID', '')))
                    if uid:
                        blocked_uids.add(uid)
                        summary = str(component.get('SUMMARY', 'evento'))
                        log_info(f"[MANUAL BLOCK] ⏸️ {summary}")
    
    except Exception as e:
        log_error(f"Error reading manual blocks: {str(e)}")
    
    if blocked_uids:
        log_success(f"Loaded {len(blocked_uids)} manual blocks")
    
    return blocked_uids

# ============================================================================
# CREATE CALENDARS
# ============================================================================

def create_import_calendar(events: List[Dict]) -> Calendar:
    """
    Create import calendar with:
    1. RESERVATION (original)
    2. TP ANTES (prep time before)
    3. TP DEPOIS (prep time after)
    """
    log_info("STEP 4: Creating import calendar (with prep times)...")
    
    import_cal = Calendar()
    import_cal.add('prodid', '-//Rental Import Calendar//PT')
    import_cal.add('version', '2.0')
    import_cal.add('calscale', 'GREGORIAN')
    import_cal.add('x-wr-calname', 'Rental Import Calendar')
    import_cal.add('x-wr-timezone', 'Europe/Lisbon')
    
    event_count = 0
    
    for event in events:
        try:
            dtstart = to_datetime(event['dtstart'])
            dtend = to_datetime(event['dtend'])
            
            if not dtstart or not dtend:
                continue
            
            source = event.get('source', 'UNKNOWN')
            uid_base = event.get('uid', '')
            summary = event.get('summary', 'Sem titulo')
            start_date = to_date(dtstart)
            end_date = to_date(dtend)
            
            # EVENT 1: ORIGINAL RESERVATION
            reserva_event = Event()
            reserva_event.add('uid', f"{uid_base}")
            reserva_event.add('summary', f"Reserva de {source}")
            reserva_event.add('dtstart', dtstart)
            reserva_event.add('dtend', dtend)
            reserva_event.add('description', f"Check-in: {start_date}\nCheck-out: {end_date}")
            reserva_event.add('location', event.get('location', ''))
            reserva_event.add('created', datetime.now(pytz.UTC))
            reserva_event.add('last-modified', datetime.now(pytz.UTC))
            reserva_event.add('status', 'CONFIRMED')
            reserva_event.add('categories', 'RESERVATION-NATIVE')
            reserva_event.add('transp', 'TRANSPARENT')
            
            import_cal.add_component(reserva_event)
            event_count += 1
            
            # EVENT 2: TP ANTES (prep time before)
            tp_before_uid = f"{uid_base}-tp-before"
            tp_before_start = start_date - timedelta(days=BUFFER_DAYS_BEFORE)
            tp_before_end = start_date
            
            tp_before_event = Event()
            tp_before_event.add('uid', tp_before_uid)
            tp_before_event.add('summary', f"TP Antes / {tp_before_start}")
            tp_before_event.add('dtstart', tp_before_start)
            tp_before_event.add('dtend', tp_before_end)
            tp_before_event.add('description', "Tempo de Preparacao")
            tp_before_event.add('location', event.get('location', ''))
            tp_before_event.add('created', datetime.now(pytz.UTC))
            tp_before_event.add('last-modified', datetime.now(pytz.UTC))
            tp_before_event.add('status', 'CONFIRMED')
            tp_before_event.add('transp', 'TRANSPARENT')
            tp_before_event.add('categories', 'PREP-TIME-BEFORE')
            tp_before_event.add('class', 'PUBLIC')
            
            import_cal.add_component(tp_before_event)
            event_count += 1
            
            # EVENT 3: TP DEPOIS (prep time after)
            tp_after_uid = f"{uid_base}-tp-after"
            tp_after_start = end_date
            tp_after_end = end_date + timedelta(days=BUFFER_DAYS_AFTER)
            
            tp_after_event = Event()
            tp_after_event.add('uid', tp_after_uid)
            tp_after_event.add('summary', f"TP Depois / {tp_after_start}")
            tp_after_event.add('dtstart', tp_after_start)
            tp_after_event.add('dtend', tp_after_end)
            tp_after_event.add('description', "Tempo de Preparacao")
            tp_after_event.add('location', event.get('location', ''))
            tp_after_event.add('created', datetime.now(pytz.UTC))
            tp_after_event.add('last-modified', datetime.now(pytz.UTC))
            tp_after_event.add('status', 'CONFIRMED')
            tp_after_event.add('transp', 'TRANSPARENT')
            tp_after_event.add('categories', 'PREP-TIME-AFTER')
            tp_after_event.add('class', 'PUBLIC')
            
            import_cal.add_component(tp_after_event)
            event_count += 1
            
        except Exception as e:
            log_error(f"Error processing event: {str(e)}")
            continue
    
    log_success(f"Import calendar created: {event_count} events ({len(events)} reservations)")
    return import_cal

def create_master_calendar(import_calendar: Calendar, blocked_uids: Set[str]) -> Calendar:
    """Create master calendar with blocked UIDs removed"""
    log_info("STEP 5: Creating master calendar (applying blocks)...")
    
    master = Calendar()
    master.add('prodid', '-//Rental Master Calendar//PT')
    master.add('version', '2.0')
    master.add('calscale', 'GREGORIAN')
    master.add('x-wr-calname', 'Rental Master Calendar')
    master.add('x-wr-timezone', 'Europe/Lisbon')
    
    event_count = 0
    skipped_count = 0
    
    try:
        for component in import_calendar.walk():
            if component.name == "VEVENT":
                uid = normalize_uid(str(component.get('UID', '')))
                
                if uid in blocked_uids:
                    summary = str(component.get('SUMMARY', 'evento'))
                    log_info(f"[BLOCK] ⏸️ Removing: {summary}")
                    skipped_count += 1
                else:
                    master.add_component(component)
                    event_count += 1
    
    except Exception as e:
        log_error(f"Error creating master: {str(e)}")
    
    log_success(f"Master created: {event_count} events (blocked: {skipped_count})")
    return master

def export_to_file(calendar: Calendar, filename: str) -> bool:
    """Export calendar to file"""
    try:
        log_info(f"Exporting to {filename}...")
        
        with open(filename, 'wb') as f:
            f.write(calendar.to_ical())
        
        file_size = os.path.getsize(filename)
        log_success(f"Saved {filename} ({file_size} bytes)")
        
        return True
    
    except Exception as e:
        log_error(f"Error exporting {filename}: {str(e)}")
        return False

# ============================================================================
# MAIN
# ============================================================================

def main() -> int:
    """Main function"""
    log_info("=" * 70)
    log_info("CALENDAR SYNCHRONIZATION - FASE 3.1")
    log_info(f"Timestamp: {datetime.now().isoformat()}")
    log_info(f"Config: TP antes={BUFFER_DAYS_BEFORE}, TP depois={BUFFER_DAYS_AFTER}")
    log_info("=" * 70)
    
    try:
        # Download calendars
        calendars = fetch_all_calendars()
        if calendars is None:
            log_error("Failed to download calendars")
            return 1
        
        # Extract events
        events = extract_events(calendars)
        if not events:
            log_error("No events extracted")
            return 2
        
        # Deduplicate
        events = deduplicate_events(events)
        
        # Load manual calendar
        manual_cal = load_manual_calendar()
        blocked_uids = get_blocked_uids(manual_cal)
        
        # Create import calendar
        import_cal = create_import_calendar(events)
        
        # Create master calendar
        master_cal = create_master_calendar(import_cal, blocked_uids)
        
        # Export files
        if not export_to_file(import_cal, IMPORT_CALENDAR_PATH):
            return 3
        
        if not export_to_file(master_cal, MASTER_CALENDAR_PATH):
            return 3
        
        # Summary
        log_info("=" * 70)
        log_success("SYNCHRONIZATION COMPLETED!")
        log_info(f"Files generated:")
        log_info(f"  - {IMPORT_CALENDAR_PATH}")
        log_info(f"  - {MASTER_CALENDAR_PATH}")
        log_info(f"  - {MANUAL_CALENDAR_PATH} (if exists)")
        log_info("=" * 70)
        
        return 0
    
    except Exception as e:
        log_error(f"Fatal error: {str(e)}")
        return 4

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    try:
        Path(REPO_PATH).mkdir(parents=True, exist_ok=True)
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        log_warning("Cancelled by user")
        sys.exit(1)
    except Exception as e:
        log_error(f"Unexpected error: {str(e)}")
        sys.exit(1)
