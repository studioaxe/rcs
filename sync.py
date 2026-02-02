#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
sync.py - Rental Calendar Sync - Core Sync Logic

Versão: 1.9 Final
Data: 01 de fevereiro de 2026
Desenvolvido por: PBrandão
"""

import os
import sys
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Any
import uuid

try:
    from icalendar import Calendar, Event
    import requests
    from dotenv import load_dotenv
    import pytz
except ImportError as e:
    print(f"ERRO de importação: {e}")
    print("Execute: pip install icalendar requests python-dotenv pytz")
    sys.exit(1)

load_dotenv()

# ============================================================
# CONFIGURAÇÃO
# ============================================================

# ✅ v2.0: Lógica de deteção de diretório robustecida para Render
def find_repo_dir() -> Path:
    """Encontra o diretório raiz do repositório, com suporte para Render."""
    # 1. Prioridade: Variável de ambiente do Render
    render_root = os.getenv('RENDER_PROJECT_ROOT')
    if render_root:
        return Path(render_root)

    # 2. Fallback: Procurar '.git' a partir do diretório atual
    work_dir = Path.cwd()
    while work_dir != Path(work_dir.root):
        if (work_dir / '.git').exists():
            return work_dir
        work_dir = work_dir.parent

    if (work_dir / '.git').exists():
        return work_dir
    
    # 3. Fallback final: Usar o diretório do script (menos fiável)
    script_dir = Path(__file__).parent.absolute()
    return script_dir

# Obter o diretório do repositório
REPO_DIR = find_repo_dir()

# Caminhos dos ficheiros - ✅ SEMPRE na raiz do repo Git
IMPORT_CALENDAR_PATH = str(REPO_DIR / 'import_calendar.ics')
MASTER_CALENDAR_PATH = str(REPO_DIR / 'master_calendar.ics')
MANUAL_CALENDAR_PATH = str(REPO_DIR / 'manual_calendar.ics')
LOG_FILE = str(REPO_DIR / 'sync.log')

# URLs
AIRBNB_ICAL_URL = os.getenv('AIRBNB_ICAL_URL', '')
BOOKING_ICAL_URL = os.getenv('BOOKING_ICAL_URL', '')
VRBO_ICAL_URL = os.getenv('VRBO_ICAL_URL', '')
BUFFER_DAYS_BEFORE = int(os.getenv('BUFFER_DAYS_BEFORE', 1))
BUFFER_DAYS_AFTER = int(os.getenv('BUFFER_DAYS_AFTER', 1))

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)

# Log inicial
logger.info(f"REPO_DIR: {REPO_DIR}")
logger.info(f"IMPORT_CALENDAR_PATH: {IMPORT_CALENDAR_PATH}")
logger.info(f"MASTER_CALENDAR_PATH: {MASTER_CALENDAR_PATH}")
logger.info(f"MANUAL_CALENDAR_PATH: {MANUAL_CALENDAR_PATH}")

# ✅ CRÍTICO: Exportar REPO_DIR para main.py poder importar
__all__ = ['sync_calendars', 'convert_events_to_nights', 'apply_night_overlay_rules', 'REPO_DIR']

# ============================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================

def to_date(dtobj) -> Optional[date]:
    """✅ v1.6: Converte QUALQUER tipo de data para date."""
    if dtobj is None:
        return None
    if hasattr(dtobj, 'dt'):
        dtobj = dtobj.dt
    if isinstance(dtobj, date) and not isinstance(dtobj, datetime):
        return dtobj
    if isinstance(dtobj, datetime):
        return dtobj.date()
    if isinstance(dtobj, str):
        dtobj = str(dtobj).strip()
        if len(dtobj) == 8 and dtobj.isdigit():
            try:
                return datetime.strptime(dtobj, '%Y%m%d').date()
            except (ValueError, TypeError):
                pass
        if len(dtobj) == 10 and dtobj.count('-') == 2:
            try:
                return datetime.strptime(dtobj, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
    return None

def to_datetime(dtobj) -> Optional[datetime]:
    """Converte para datetime com UTC."""
    if dtobj is None:
        return None
    if hasattr(dtobj, 'dt'):
        dtobj = dtobj.dt
    if isinstance(dtobj, datetime):
        if dtobj.tzinfo is None:
            return dtobj.replace(tzinfo=pytz.UTC)
        return dtobj
    if isinstance(dtobj, date):
        return datetime.combine(dtobj, datetime.min.time()).replace(tzinfo=pytz.UTC)
    return None

def normalize_uid(uid: str) -> str:
    """Normaliza UID."""
    if not uid:
        return ''
    return str(uid).strip().lower()

def clean_description(text: str) -> str:
    """Limpa descrição."""
    if not text:
        return ''
    text = text.replace('\r\n', ' ').replace('\n', ' ')
    while '  ' in text:
        text = text.replace('  ', ' ')
    return text.strip()

def log_info(msg: str) -> None:
    logger.info(msg)
    print(f"[INFO] {msg}")

def log_warning(msg: str) -> None:
    logger.warning(msg)
    print(f"[WARNING] {msg}")

def log_error(msg: str) -> None:
    logger.error(msg)
    print(f"[ERROR] {msg}")

def log_success(msg: str) -> None:
    logger.info(msg)
    print(f"[SUCCESS] {msg}")

# ============================================================
# NOITES (NIGHTS)
# ============================================================

def convert_events_to_nights(events: List[Dict]) -> Dict[str, Dict]:
    """✅ v1.6: Converte eventos para mapa de NOITES."""
    night_map: Dict[str, Dict] = {}
    for event in events:
        dtstart = to_date(event.get('dtstart'))
        dtend = to_date(event.get('dtend'))
        categories = event.get('categories', 'UNKNOWN')
        description = event.get('description', '')
        uid = event.get('uid', '')
        
        if not dtstart or not dtend:
            continue
        
        current = dtstart
        while current < dtend:
            night_date_str = current.isoformat()
            night_map[night_date_str] = {
                'category': categories,
                'description': description,
                'uid': uid,
            }
            current += timedelta(days=1)
    
    log_info(f"[NIGHTS] Convertidos {len(events)} eventos → {len(night_map)} noites")
    return night_map

def apply_night_overlay_rules(import_nights: Dict[str, Dict],
                               manual_nights: Dict[str, Dict]) -> Dict[str, Dict]:
    """✅ Aplica regras de sobrecarga."""
    final_nights = dict(import_nights)
    
    for night_date, manual_event in manual_nights.items():
        import_event = import_nights.get(night_date)
        import_category = import_event['category'] if import_event else None
        manual_category = manual_event['category']
        
        if import_category == 'RESERVATION':
            log_info(f"[OVERLAY] {night_date}: RESERVATION é soberana")
            continue
        
        if manual_category == 'MANUAL-REMOVE':
            log_success(f"[OVERLAY] {night_date}: MANUAL-REMOVE sobrepõe PREP-TIME")
            final_nights[night_date] = manual_event
        elif manual_category == 'MANUAL-BLOCK':
            if not import_event or import_category == 'AVAILABLE':
                log_success(f"[OVERLAY] {night_date}: MANUAL-BLOCK bloqueia")
                final_nights[night_date] = manual_event
        else:
            final_nights[night_date] = manual_event
    
    return final_nights

# ============================================================================
# FUNÇÕES PRINCIPAIS
# ============================================================================

def download_calendar(url: str, source: str) -> Optional[Calendar]:
    """Download calendar."""
    try:
        if not url:
            log_warning(f"Nenhuma URL para {source}")
            return None
        
        log_info(f"[IMPORT] Downloading {source}...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        cal = Calendar.from_ical(response.content)
        events = [c for c in cal.walk() if c.name == 'VEVENT']
        log_success(f"Downloaded {len(events)} events from {source}")
        return cal
    except Exception as e:
        log_error(f"Erro ao descarregar {source}: {e}")
        return None

def fetch_all_calendars(force_download: bool = False) -> Optional[Dict[str, Optional[Calendar]]]:
    """Download all calendars or load from import_calendar.ics if it exists.
    
    Args:
        force_download: Se True, força download fresco ignorando cache local
    """
    log_info("STEP 1: Importing calendars...")
    
    if not force_download:
        try:
            path = Path(IMPORT_CALENDAR_PATH)
            if path.exists():
                log_info(f"Loading existing {IMPORT_CALENDAR_PATH}...")
                with path.open('rb') as f:
                    cal = Calendar.from_ical(f.read())
                return {
                    'IMPORT': cal,
                    'AIRBNB': None,
                    'BOOKING': None,
                    'VRBO': None,
                }
        except Exception as e:
            log_warning(f"Error loading existing import_calendar.ics: {e}")
    else:
        log_info("🔄 FORCE DOWNLOAD: Ignorando cache, baixando calendários frescos...")
    
    calendars = {
        'AIRBNB': download_calendar(AIRBNB_ICAL_URL, 'AIRBNB'),
        'BOOKING': download_calendar(BOOKING_ICAL_URL, 'BOOKING'),
        'VRBO': download_calendar(VRBO_ICAL_URL, 'VRBO'),
    }
    
    if all(v is None for v in calendars.values()):
        log_error("ERROR: No calendar imported and import_calendar.ics does not exist")
        return None
    
    return calendars

def extract_events(calendars: Dict[str, Optional[Calendar]]) -> List[Dict]:
    """Extract events."""
    log_info("STEP 2: Extracting events...")
    all_events: List[Dict] = []
    
    for source, cal in calendars.items():
        if cal is None:
            continue
        
        try:
            for component in cal.walk():
                if component.name != 'VEVENT':
                    continue
                
                categories_raw = component.get('CATEGORIES')
                if categories_raw:
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
                        'already_processed': True,
                    }
                    all_events.append(event)
                    continue
                
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
                    'already_processed': False,
                }
                all_events.append(event)
        except Exception as e:
            log_error(f"Erro ao extrair de {source}: {e}")
    
    log_info(f"Extracted {len(all_events)} events total")
    return all_events

def deduplicate_events(events: List[Dict]) -> List[Dict]:
    """Deduplicate events."""
    log_info("STEP 3: Deduplicating events...")
    
    if not events:
        return []
    
    groups: Dict = {}
    for event in events:
        key = (to_date(event['dtstart']), to_date(event['dtend']), event['summary'])
        groups.setdefault(key, []).append(event)
    
    deduplicated: List[Dict] = []
    for _, group in groups.items():
        best = max(group, key=lambda e: len(e.get('description', '')))
        deduplicated.append(best)
    
    removed = len(events) - len(deduplicated)
    if removed > 0:
        log_warning(f"Removidos {removed} duplicatas")
    
    return deduplicated

def load_manual_calendar() -> Optional[Calendar]:
    """Load manual calendar."""
    try:
        path = Path(MANUAL_CALENDAR_PATH)
        if not path.exists():
            log_info(f"Nenhum manual_calendar.ics encontrado")
            return None
        
        with path.open('rb') as f:
            cal = Calendar.from_ical(f.read())
        log_info(f"Loaded {MANUAL_CALENDAR_PATH}")
        return cal
    except Exception as e:
        log_error(f"Erro ao carregar manual calendar: {e}")
        return None

def get_manual_removes(manual_calendar: Optional[Calendar]) -> Set[Tuple[date, date]]:
    """✅ v1.6: Extrai MANUAL-REMOVE."""
    remove_ranges: Set[Tuple[date, date]] = set()
    
    if manual_calendar is None:
        return remove_ranges
    
    try:
        for component in manual_calendar.walk():
            if component.name != 'VEVENT':
                continue
            
            categories_raw = component.get('CATEGORIES')
            if not categories_raw:
                continue
            
            if hasattr(categories_raw, 'to_ical'):
                try:
                    categories_str = categories_raw.to_ical().decode().upper()
                except Exception:
                    categories_str = str(categories_raw).upper()
            else:
                categories_str = str(categories_raw).upper()
            
            if 'MANUAL-REMOVE' not in categories_str:
                continue
            
            dtstart = component.get('DTSTART')
            dtend = component.get('DTEND')
            start_date = to_date(dtstart)
            end_date = to_date(dtend)
            
            if start_date and end_date:
                date_range = (start_date, end_date)
                remove_ranges.add(date_range)
                summary = str(component.get('SUMMARY', 'evento'))
                log_success(f"[MANUAL-REMOVE] {summary} ({start_date} a {end_date})")
    except Exception as e:
        log_error(f"Erro ao ler manual removes: {e}")
    
    return remove_ranges

def get_manual_blocks(manual_calendar: Optional[Calendar]) -> List[Dict]:
    """Get manual blocks."""
    blocks: List[Dict] = []
    
    if not manual_calendar:
        return blocks
    
    try:
        for component in manual_calendar.walk():
            if component.name != 'VEVENT':
                continue
            
            categories_raw = component.get('CATEGORIES')
            if not categories_raw:
                continue
            
            if hasattr(categories_raw, 'to_ical'):
                try:
                    categories_str = categories_raw.to_ical().decode().upper()
                except Exception:
                    categories_str = str(categories_raw).upper()
            else:
                categories_str = str(categories_raw).upper()
            
            if 'MANUAL-BLOCK' not in categories_str:
                continue
            
            dtstart = component.get('DTSTART')
            dtend = component.get('DTEND')
            block = {
                'uid': str(component.get('UID', '')),
                'summary': str(component.get('SUMMARY', 'Bloqueado')),
                'dtstart': dtstart.dt if dtstart else None,
                'dtend': dtend.dt if dtend else None,
                'description': str(component.get('DESCRIPTION', '')),
                'component': component,
            }
            blocks.append(block)
            log_info(f"[MANUAL-BLOCK FOUND] {block['summary']}")
        
        if blocks:
            log_success(f"Loaded {len(blocks)} manual blocks")
    except Exception as e:
        log_error(f"Erro ao ler manual blocks: {e}")
    
    return blocks

def create_import_calendar(events: List[Dict]) -> Calendar:
    """Create import calendar."""
    log_info("STEP 4: Creating import_calendar.ics...")
    
    cal = Calendar()
    cal.add('prodid', '-//Rental Import Calendar//PT')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('x-wr-calname', 'Import Calendar Auto')
    cal.add('x-wr-timezone', 'Europe/Lisbon')
    
    event_count = 0
    
    for event in events:
        try:
            if event.get('already_processed'):
                cal.add_component(event['component'])
                event_count += 1
                continue
            
            dtstart = to_datetime(event['dtstart'])
            dtend = to_datetime(event['dtend'])
            
            if not dtstart or not dtend:
                continue
            
            source = event.get('source', 'UNKNOWN')
            uid_base = event.get('uid', '')
            start_date = to_date(dtstart)
            end_date = to_date(dtend)
            
            # Reserva
            reserva_event = Event()
            reserva_event.add('uid', uid_base)
            reserva_event.add('summary', f"Reserva {source} {start_date} a {end_date}")
            reserva_event.add('dtstart', start_date)
            reserva_event.add('dtend', end_date)
            reserva_event.add('description', clean_description(
                f"{source}. Check-in: {start_date}. Check-out: {end_date}"
            ))
            reserva_event.add('location', event.get('location', ''))
            reserva_event.add('created', datetime.now(pytz.UTC))
            reserva_event.add('last-modified', datetime.now(pytz.UTC))
            reserva_event.add('status', 'CONFIRMED')
            reserva_event.add('categories', 'RESERVATION')
            reserva_event.add('transp', 'TRANSPARENT')
            cal.add_component(reserva_event)
            event_count += 1
            
            # TP Antes
            tp_before_uid = f"{uid_base}-tp-before"
            tp_before_start = start_date - timedelta(days=BUFFER_DAYS_BEFORE)
            tp_before_end = start_date
            tp_before_event = Event()
            tp_before_event.add('uid', tp_before_uid)
            tp_before_event.add('summary', f"TP Antes {source} {tp_before_start} a {start_date}")
            tp_before_event.add('dtstart', tp_before_start)
            tp_before_event.add('dtend', tp_before_end)
            tp_before_event.add('description', clean_description(
                f"Tempo de Preparação. Associado a Reserva {source} de {start_date} a {end_date}"
            ))
            tp_before_event.add('location', event.get('location', ''))
            tp_before_event.add('created', datetime.now(pytz.UTC))
            tp_before_event.add('last-modified', datetime.now(pytz.UTC))
            tp_before_event.add('status', 'CONFIRMED')
            tp_before_event.add('transp', 'TRANSPARENT')
            tp_before_event.add('categories', 'PREP-TIME')
            tp_before_event.add('class', 'PUBLIC')
            cal.add_component(tp_before_event)
            event_count += 1
            
            # TP Depois
            tp_after_uid = f"{uid_base}-tp-after"
            tp_after_start = end_date
            tp_after_end = end_date + timedelta(days=BUFFER_DAYS_AFTER)
            tp_after_event = Event()
            tp_after_event.add('uid', tp_after_uid)
            tp_after_event.add('summary', f"TP Depois {source} {end_date} a {tp_after_end}")
            tp_after_event.add('dtstart', tp_after_start)
            tp_after_event.add('dtend', tp_after_end)
            tp_after_event.add('description', clean_description(
                f"Tempo de Preparação. Associado a Reserva {source} de {start_date} a {end_date}"
            ))
            tp_after_event.add('location', event.get('location', ''))
            tp_after_event.add('created', datetime.now(pytz.UTC))
            tp_after_event.add('last-modified', datetime.now(pytz.UTC))
            tp_after_event.add('status', 'CONFIRMED')
            tp_after_event.add('transp', 'TRANSPARENT')
            tp_after_event.add('categories', 'PREP-TIME')
            tp_after_event.add('class', 'PUBLIC')
            cal.add_component(tp_after_event)
            event_count += 1
        except Exception as e:
            log_error(f"Erro ao processar evento: {e}")
    
    log_success(f"Created import_calendar with {event_count} events ({len(events)} reservations)")
    return cal

def merge_calendars(import_cal: Calendar, manual_cal: Optional[Calendar]) -> Calendar:
    """✅ v1.6: Merge com to_date() CORRIGIDA."""
    log_info("STEP 5: Merging calendars (import + manual)...")
    
    master_cal = Calendar()
    master_cal.add('prodid', '-//Rental Master Calendar//PT')
    master_cal.add('version', '2.0')
    master_cal.add('calscale', 'GREGORIAN')
    master_cal.add('x-wr-calname', 'Master Calendar Final')
    master_cal.add('x-wr-timezone', 'Europe/Lisbon')
    
    manual_blocks = get_manual_blocks(manual_cal)
    manual_removes = get_manual_removes(manual_cal)
    log_info(f"[MERGE] Processando: {len(manual_blocks)} MANUAL-BLOCK, {len(manual_removes)} MANUAL-REMOVE")
    
    included = 0
    removed = 0
    prep_time_removed = 0
    reservations_included = 0
    
    for component in import_cal.walk():
        if component.name != 'VEVENT':
            continue
        
        uid = normalize_uid(str(component.get('UID', '')))
        categories_raw = component.get('CATEGORIES')
        
        if hasattr(categories_raw, 'to_ical'):
            try:
                categories = categories_raw.to_ical().decode().upper()
            except Exception:
                categories = str(categories_raw).upper()
        else:
            categories = str(categories_raw).upper()
        
        summary = str(component.get('SUMMARY', '?'))
        
        if 'RESERVATION' in categories:
            log_info(f"[MERGE] Evento adicional: {summary}")
            master_cal.add_component(component)
            included += 1
            reservations_included += 1
            continue
        
        if 'PREP-TIME' in categories:
            dtstart = component.get('DTSTART')
            dtend = component.get('DTEND')
            start_date = to_date(dtstart)
            end_date = to_date(dtend)
            event_range = (start_date, end_date) if (start_date and end_date) else None
            
            if event_range and event_range in manual_removes:
                log_warning(f"[MERGE] PREP-TIME removida: {summary}")
                prep_time_removed += 1
                removed += 1
                continue
            
            log_info(f"[MERGE] Evento adicional: {summary}")
            master_cal.add_component(component)
            included += 1
            continue
        
        log_info(f"[MERGE] Evento adicional: {summary}")
        master_cal.add_component(component)
        included += 1
    
    for block in manual_blocks:
        block_summary = block.get('summary', '?')
        log_info(f"[MERGE] Adicionando MANUAL-BLOCK: {block_summary}")
        master_cal.add_component(block['component'])
        included += 1
    
    log_success(f"[MERGE] Calendarios mesclados:")
    log_success(f" - RESERVATION (soberanas): {reservations_included} eventos")
    log_success(f" - PREP-TIME removidas: {prep_time_removed} eventos")
    log_success(f" - MANUAL-BLOCK adicionadas: {len(manual_blocks)} eventos")
    log_success(f" - TOTAL no master: {included} eventos")
    
    return master_cal

def export_to_file(cal: Calendar, filepath: str) -> bool:
    """Export calendar."""
    try:
        # Garantir que a pasta existe
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # Gerar ICS
        ical_data = cal.to_ical()
        
        # Remover line continuations
        ical_data = ical_data.replace(b'\r\n ', b'').replace(b'\n ', b'')
        
        with open(filepath, 'wb') as f:
            f.write(ical_data)
        
        filesize = os.path.getsize(filepath)
        log_success(f"Exported {filepath} ({filesize} bytes)")
        return True
    except Exception as e:
        log_error(f"Erro ao exportar {filepath}: {e}")
        return False

def sync_local(force_download: bool = False) -> Dict[str, Any]:
    """Main sync.
    
    Args:
        force_download: Se True, força download fresco de calendários externos
    """
    try:
        calendars = fetch_all_calendars(force_download=force_download)
        if calendars is None:
            return {'status': 'error', 'message': 'Nenhum calendário importado'}
        
        events = extract_events(calendars)
        if not events:
            return {'status': 'error', 'message': 'Nenhum evento encontrado'}
        
        events = deduplicate_events(events)
        import_cal = create_import_calendar(events)
        manual_cal = load_manual_calendar()
        master_cal = merge_calendars(import_cal, manual_cal)
        
        if not export_to_file(import_cal, IMPORT_CALENDAR_PATH):
            return {'status': 'error', 'message': 'Falha ao gravar import_calendar.ics'}
        
        if not export_to_file(master_cal, MASTER_CALENDAR_PATH):
            return {'status': 'error', 'message': 'Falha ao gravar master_calendar.ics'}
        
        import_events = len([c for c in import_cal.walk() if c.name == 'VEVENT'])
        manual_events = len([c for c in manual_cal.walk() if c.name == 'VEVENT']) if manual_cal else 0
        master_events = len([c for c in master_cal.walk() if c.name == 'VEVENT'])
        
        return {
            'status': 'success',
            'message': '✅ Sincronização concluída!',
            'events_downloaded': len(events),
            'import_count': import_events,
            'manual_count': manual_events,
            'master_count': master_events,
            'timestamp': datetime.now().isoformat(),
        }
    except Exception as e:
        log_error(f"Sync failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        return {'status': 'error', 'message': str(e)}

def sync_calendars(force_download: bool = False) -> bool:
    """Compatibilidade com main.py.
    
    Args:
        force_download: Se True, força download fresco ignorando cache
    """
    result = sync_local(force_download=force_download)
    return result.get('status') == 'success'

if __name__ == '__main__':
    log_info('=' * 70)
    log_info('CALENDAR SYNCHRONIZATION - v1.9 FINAL (Force Download)')
    log_info(f'Timestamp: {datetime.now().isoformat()}')
    log_info(f'Config: TP antes={BUFFER_DAYS_BEFORE}d, TP depois={BUFFER_DAYS_AFTER}d')
    log_info(f'Repo directory: {REPO_DIR}')
    log_info('=' * 70)
    
    # CLI sempre força download
    result = sync_local(force_download=True)
    
    if result.get('status') == 'error':
        log_error(f"SYNC FAILED: {result.get('message')}")
        sys.exit(1)
    else:
        log_success('SYNC COMPLETED SUCCESSFULLY')
        print()
        print(f"Events downloaded: {result.get('events_downloaded', 0)}")
        print(f"Import calendar: {result.get('import_count', 0)} events")
        print(f"Manual calendar: {result.get('manual_count', 0)} events")
        print(f"Master calendar: {result.get('master_count', 0)} events")
        print()
        sys.exit(0)
