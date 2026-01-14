#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync.py - Sincronização de calendários e Gestor Manual de Calendários
Versão: 4.0
Data: 14 de Janeiro de 2026
Desenvolvido por: PBrandão

Novo: Classe ManualCalendarManager para operações CRUD no manual_calendar.ics
"""
import os
import sys
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Dict, Optional, Set, Any
import uuid

# ============================================================
# IMPORTS
# ============================================================
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
# CONFIGURAÇÃO DE PATHS
# ============================================================
REPO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# URLs dos calendários
AIRBNB_ICAL_URL = os.getenv('AIRBNB_ICAL_URL', '')
BOOKING_ICAL_URL = os.getenv('BOOKING_ICAL_URL', '')
VRBO_ICAL_URL = os.getenv('VRBO_ICAL_URL', '')

# Tempo de preparação
BUFFER_DAYS_BEFORE = int(os.getenv('BUFFER_DAYS_BEFORE', 1))
BUFFER_DAYS_AFTER = int(os.getenv('BUFFER_DAYS_AFTER', 1))

# Ficheiros
IMPORT_CALENDAR_PATH = os.path.join(REPO_PATH, 'import_calendar.ics')
MASTER_CALENDAR_PATH = os.path.join(REPO_PATH, 'master_calendar.ics')
MANUAL_CALENDAR_PATH = os.path.join(REPO_PATH, 'manual_calendar.ics')
LOG_FILE = os.path.join(REPO_PATH, 'sync.log')

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


# ============================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================
def to_datetime(dtobj) -> Optional[datetime]:
    """Converte date/datetime em datetime com timezone UTC."""
    if dtobj is None:
        return None
    if isinstance(dtobj, datetime):
        if dtobj.tzinfo is None:
            return dtobj.replace(tzinfo=pytz.UTC)
        return dtobj
    if isinstance(dtobj, date):
        return datetime.combine(dtobj, datetime.min.time()).replace(tzinfo=pytz.UTC)
    return None


def to_date(dtobj) -> Optional[date]:
    """Converte datetime em date."""
    if dtobj is None:
        return None
    if isinstance(dtobj, datetime):
        return dtobj.date()
    if isinstance(dtobj, date):
        return dtobj
    return None


def normalize_uid(uid: str) -> str:
    """Normaliza UID para comparação."""
    if not uid:
        return ''
    return str(uid).strip().lower()


def clean_description(text: str) -> str:
    """Remove espaçamentos e quebras desnecessárias."""
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
# GESTOR MANUAL DE CALENDÁRIO (NOVO v4.0)
# ============================================================
class ManualCalendarManager:
    """Gerencia operações CRUD no manual_calendar.ics"""
    
    def __init__(self):
        self.manual_events = []
        self.load_manual_events_into_memory()
    
    def load_manual_events_into_memory(self) -> None:
        """Carrega eventos do manual_calendar.ics na memória"""
        try:
            if Path(MANUAL_CALENDAR_PATH).exists():
                with open(MANUAL_CALENDAR_PATH, 'rb') as f:
                    cal = Calendar.from_ical(f.read())
                    for component in cal.walk():
                        if component.name == 'VEVENT':
                            self.manual_events.append(component)
            else:
                self.manual_events = []
        except Exception as e:
            log_error(f"Erro ao carregar manual_events na memória: {e}")
            self.manual_events = []
    
    def load_import_events(self) -> List[Dict]:
        """Retorna lista de eventos do import_calendar.ics"""
        try:
            if not Path(IMPORT_CALENDAR_PATH).exists():
                return []
            
            events = []
            with open(IMPORT_CALENDAR_PATH, 'rb') as f:
                cal = Calendar.from_ical(f.read())
                for component in cal.walk():
                    if component.name != 'VEVENT':
                        continue
                    
                    dtstart = component.get('DTSTART')
                    dtend = component.get('DTEND')
                    
                    event = {
                        'uid': str(component.get('UID', '')),
                        'summary': str(component.get('SUMMARY', '')),
                        'description': str(component.get('DESCRIPTION', '')),
                        'dtstart': dtstart.dt.isoformat() if dtstart else None,
                        'dtend': dtend.dt.isoformat() if dtend else None,
                        'categories': str(component.get('CATEGORIES', '')),
                    }
                    events.append(event)
            
            return events
        except Exception as e:
            log_error(f"Erro ao carregar import_events: {e}")
            return []
    
    def load_manual_events(self) -> List[Dict]:
        """Retorna lista de eventos do manual_calendar.ics"""
        try:
            events = []
            for component in self.manual_events:
                dtstart = component.get('DTSTART')
                dtend = component.get('DTEND')
                
                event = {
                    'uid': str(component.get('UID', '')),
                    'summary': str(component.get('SUMMARY', '')),
                    'description': str(component.get('DESCRIPTION', '')),
                    'dtstart': dtstart.dt.isoformat() if dtstart else None,
                    'dtend': dtend.dt.isoformat() if dtend else None,
                    'categories': str(component.get('CATEGORIES', '')),
                }
                events.append(event)
            
            return events
        except Exception as e:
            log_error(f"Erro ao carregar manual_events: {e}")
            return []
    
    def block_dates(self, dates: List[str]) -> bool:
        """
        Bloqueia datas (MANUAL-BLOCK)
        dates: Lista de datas em formato YYYY-MM-DD
        """
        try:
            for date_str in dates:
                # Validar formato
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    log_error(f"Formato de data inválido: {date_str}")
                    continue
                
                # Criar evento MANUAL-BLOCK
                event = Event()
                event.add('uid', f"manual-block-{date_str}-{uuid.uuid4()}")
                event.add('summary', date_str)
                event.add('description', 'Data Bloqueada Manualmente')
                event.add('dtstart', date_obj)
                event.add('dtend', date_obj + timedelta(days=1))
                event.add('categories', 'MANUAL-BLOCK')
                event.add('created', datetime.now(pytz.UTC))
                event.add('last-modified', datetime.now(pytz.UTC))
                event.add('status', 'CONFIRMED')
                event.add('transp', 'TRANSPARENT')
                
                self.manual_events.append(event)
                log_info(f"[MANUAL-BLOCK] {date_str}")
            
            log_success(f"Bloqueadas {len(dates)} data(s)")
            return True
        except Exception as e:
            log_error(f"Erro ao bloquear datas: {e}")
            return False
    
    def remove_events(self, dates: List[str]) -> bool:
        """
        Remove eventos (MANUAL-REMOVE)
        dates: Lista de datas em formato YYYY-MM-DD
        """
        try:
            for date_str in dates:
                # Validar formato
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    log_error(f"Formato de data inválido: {date_str}")
                    continue
                
                # Criar evento MANUAL-REMOVE
                event = Event()
                event.add('uid', f"manual-remove-{date_str}-{uuid.uuid4()}")
                event.add('summary', date_str)
                event.add('description', 'Data Desbloqueada Manualmente')
                event.add('dtstart', date_obj)
                event.add('dtend', date_obj + timedelta(days=1))
                event.add('categories', 'MANUAL-REMOVE')
                event.add('created', datetime.now(pytz.UTC))
                event.add('last-modified', datetime.now(pytz.UTC))
                event.add('status', 'CONFIRMED')
                event.add('transp', 'TRANSPARENT')
                
                self.manual_events.append(event)
                log_info(f"[MANUAL-REMOVE] {date_str}")
            
            log_success(f"Removidas {len(dates)} data(s)")
            return True
        except Exception as e:
            log_error(f"Erro ao remover eventos: {e}")
            return False
    
    def clear_events(self, dates: List[str]) -> bool:
        """
        Limpa eventos das datas especificadas do manual_calendar.ics
        dates: Lista de datas em formato YYYY-MM-DD
        """
        try:
            for date_str in dates:
                # Validar formato
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    log_error(f"Formato de data inválido: {date_str}")
                    continue
                
                # Remover eventos dessa data
                self.manual_events = [
                    event for event in self.manual_events
                    if to_date(event.get('DTSTART').dt) != date_obj
                ]
                
                log_info(f"[CLEAR] {date_str}")
            
            log_success(f"Limpas {len(dates)} data(s)")
            return True
        except Exception as e:
            log_error(f"Erro ao limpar eventos: {e}")
            return False
    
    def save_manual_calendar(self) -> bool:
        """Guarda manual_events em manual_calendar.ics"""
        try:
            cal = Calendar()
            cal.add('prodid', '-//Rental Manual Calendar//PT')
            cal.add('version', '2.0')
            cal.add('calscale', 'GREGORIAN')
            cal.add('x-wr-calname', 'Manual Calendar')
            cal.add('x-wr-timezone', 'Europe/Lisbon')
            
            for event in self.manual_events:
                cal.add_component(event)
            
            ical_data = cal.to_ical()
            with open(MANUAL_CALENDAR_PATH, 'wb') as f:
                f.write(ical_data)
            
            log_success(f"Saved {MANUAL_CALENDAR_PATH} ({len(self.manual_events)} events)")
            return True
        except Exception as e:
            log_error(f"Erro ao guardar manual_calendar.ics: {e}")
            return False


# ============================================================
# DOWNLOAD E PROCESSAMENTO (Mantido do original)
# ============================================================
def download_calendar(url: str, source: str) -> Optional[Calendar]:
    """Descarrega calendário de URL iCal."""
    try:
        if not url:
            log_warning(f"Nenhuma URL configurada para {source}")
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


def fetch_all_calendars() -> Optional[Dict[str, Optional[Calendar]]]:
    """Descarrega todos os calendários."""
    log_info("STEP 1: Importing calendars...")
    
    calendars = {
        'AIRBNB': download_calendar(AIRBNB_ICAL_URL, 'AIRBNB'),
        'BOOKING': download_calendar(BOOKING_ICAL_URL, 'BOOKING'),
        'VRBO': download_calendar(VRBO_ICAL_URL, 'VRBO'),
    }
    
    if all(v is None for v in calendars.values()):
        log_error("ERRO: Nenhum calendário foi importado com sucesso")
        return None
    
    return calendars


def extract_events(calendars: Dict[str, Optional[Calendar]]) -> List[Dict]:
    """Extrai eventos de todos os calendários."""
    log_info("STEP 2: Extracting events...")
    
    all_events: List[Dict] = []
    
    for source, cal in calendars.items():
        if cal is None:
            continue
        
        try:
            for component in cal.walk():
                if component.name != 'VEVENT':
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
                }
                
                all_events.append(event)
        except Exception as e:
            log_error(f"Erro ao extrair de {source}: {e}")
            continue
    
    log_info(f"Extracted {len(all_events)} events total")
    return all_events


def deduplicate_events(events: List[Dict]) -> List[Dict]:
    """Remove eventos duplicados."""
    log_info("STEP 3: Deduplicating events...")
    
    if not events:
        log_warning("Nenhum evento para desduplicar")
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
    """Carrega calendário manual."""
    try:
        path = Path(MANUAL_CALENDAR_PATH)
        if not path.exists():
            log_info(f"Nenhum {MANUAL_CALENDAR_PATH} encontrado")
            return None
        
        with path.open('rb') as f:
            cal = Calendar.from_ical(f.read())
        
        log_info(f"Loaded {MANUAL_CALENDAR_PATH}")
        return cal
    except Exception as e:
        log_error(f"Erro ao carregar manual calendar: {e}")
        return None


def get_manual_blocks(manual_calendar: Optional[Calendar]) -> List[Dict]:
    """Retorna eventos com CATEGORIES:MANUAL-BLOCK."""
    blocks: List[Dict] = []
    
    if not manual_calendar:
        return blocks
    
    try:
        for component in manual_calendar.walk():
            if component.name != 'VEVENT':
                continue
            
            categories = str(component.get('CATEGORIES', '')).upper()
            if 'MANUAL-BLOCK' not in categories:
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
            log_info(f"[MANUAL BLOCK] {block['summary']}")
        
        if blocks:
            log_success(f"Loaded {len(blocks)} manual blocks")
    except Exception as e:
        log_error(f"Erro ao ler manual blocks: {e}")
    
    return blocks


def get_manual_removes(manual_calendar: Optional[Calendar]) -> Set[str]:
    """Retorna UIDs com CATEGORIES:MANUAL-REMOVE."""
    remove_uids: Set[str] = set()
    
    if not manual_calendar:
        return remove_uids
    
    try:
        for component in manual_calendar.walk():
            if component.name != 'VEVENT':
                continue
            
            categories = str(component.get('CATEGORIES', '')).upper()
            if 'MANUAL-REMOVE' not in categories:
                continue
            
            uid = normalize_uid(str(component.get('UID', '')))
            if uid:
                remove_uids.add(uid)
            
            summary = str(component.get('SUMMARY', 'evento'))
            log_info(f"[MANUAL REMOVE] {summary}")
        
        if remove_uids:
            log_success(f"Loaded {len(remove_uids)} manual removes")
    except Exception as e:
        log_error(f"Erro ao ler manual removes: {e}")
    
    return remove_uids


def create_import_calendar(events: List[Dict]) -> Calendar:
    """Cria import_calendar.ics."""
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
            dtstart = to_datetime(event['dtstart'])
            dtend = to_datetime(event['dtend'])
            
            if not dtstart or not dtend:
                continue
            
            source = event.get('source', 'UNKNOWN')
            uid_base = event.get('uid', '')
            start_date = to_date(dtstart)
            end_date = to_date(dtend)
            
            # Reserva nativa
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
            reserva_event.add('categories', 'RESERVATION-NATIVE')
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
            tp_before_event.add('categories', 'PREP-TIME-BEFORE')
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
            tp_after_event.add('categories', 'PREP-TIME-AFTER')
            tp_after_event.add('class', 'PUBLIC')
            
            cal.add_component(tp_after_event)
            event_count += 1
            
        except Exception as e:
            log_error(f"Erro ao processar evento: {e}")
            continue
    
    log_success(f"Created import_calendar with {event_count} events ({len(events)} reservations)")
    return cal


def create_master_calendar(
    import_cal: Calendar,
    manual_removes: Set[str],
    manual_blocks: List[Dict],
) -> Calendar:
    """Cria master_calendar.ics."""
    log_info("STEP 5: Creating master_calendar.ics...")
    
    cal = Calendar()
    cal.add('prodid', '-//Rental Master Calendar//PT')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('x-wr-calname', 'Master Calendar Final')
    cal.add('x-wr-timezone', 'Europe/Lisbon')
    cal.add('x-wr-caldesc', clean_description(
        'Master Calendar para Rental Calendar Sync - Desenvolvido por P.Brandao'
    ))
    
    included = 0
    blocked = 0
    
    try:
        # Copiar eventos de import_calendar, excluindo removidos
        for component in import_cal.walk():
            if component.name != 'VEVENT':
                continue
            
            uid = normalize_uid(str(component.get('UID', '')))
            
            if uid in manual_removes:
                log_warning(f"BLOCKED manual: {component.get('SUMMARY', '?')}")
                blocked += 1
                continue
            
            cal.add_component(component)
            included += 1
        
        # Adicionar bloqueios manuais
        for idx, block in enumerate(manual_blocks):
            try:
                block_event = Event()
                block_event.add('uid', f"manual-block-{idx}-{datetime.now().timestamp()}")
                block_event.add('summary', f"🔒 BLOQUEADO {block['summary']}")
                block_event.add('dtstart', to_date(block['dtstart']))
                block_event.add('dtend', to_date(block['dtend']))
                block_event.add('description', clean_description(
                    block['description'] or 'Data bloqueada manualmente'
                ))
                block_event.add('categories', 'MANUAL-BLOCK')
                block_event.add('status', 'CONFIRMED')
                block_event.add('transp', 'TRANSPARENT')
                block_event.add('created', datetime.now(pytz.UTC))
                block_event.add('last-modified', datetime.now(pytz.UTC))
                
                cal.add_component(block_event)
                included += 1
                
                log_info(f"[BLOCK] Added {block['summary']}")
            except Exception as e:
                log_error(f"Erro ao adicionar block: {e}")
                continue
    
    except Exception as e:
        log_error(f"Erro ao criar master: {e}")
    
    log_success(f"Created master_calendar: {included} included, {blocked} blocked")
    return cal


def export_to_file(cal: Calendar, filepath: str) -> bool:
    """Guarda calendário em ficheiro ICS."""
    try:
        ical_data = cal.to_ical()
        ical_data = ical_data.replace(b'\r\n ', b'').replace(b'\n ', b'')
        
        with open(filepath, 'wb') as f:
            f.write(ical_data)
        
        filesize = os.path.getsize(filepath)
        log_success(f"Exported {filepath} ({filesize} bytes)")
        return True
    except Exception as e:
        log_error(f"Erro ao exportar {filepath}: {e}")
        return False


def sync_local() -> Dict[str, Any]:
    """
    Executa pipeline completo de sincronização.
    Retorna Dict com status, contagens de eventos, etc.
    """
    try:
        # 1. Download
        calendars = fetch_all_calendars()
        if calendars is None:
            return {
                'status': 'error',
                'message': 'Nenhum calendário importado com sucesso',
            }
        
        # 2. Extração
        events = extract_events(calendars)
        if not events:
            return {
                'status': 'error',
                'message': 'Nenhum evento encontrado',
            }
        
        # 3. Deduplicação
        events = deduplicate_events(events)
        
        # 4. Carregamento de manual calendar
        manual_cal = None
        manual_removes = set()
        manual_blocks = []
        
        if Path(MANUAL_CALENDAR_PATH).is_file():
            manual_cal = load_manual_calendar()
            if manual_cal:
                manual_removes = get_manual_removes(manual_cal)
                manual_blocks = get_manual_blocks(manual_cal)
        
        # 5. Criação
        import_cal = create_import_calendar(events)
        master_cal = create_master_calendar(import_cal, manual_removes, manual_blocks)
        
        # 6. Exportação
        if not export_to_file(import_cal, IMPORT_CALENDAR_PATH):
            return {
                'status': 'error',
                'message': 'Falha ao gravar import_calendar.ics',
            }
        
        if not export_to_file(master_cal, MASTER_CALENDAR_PATH):
            return {
                'status': 'error',
                'message': 'Falha ao gravar master_calendar.ics',
            }
        
        # 7. Contagens
        import_events = len([c for c in import_cal.walk() if c.name == 'VEVENT'])
        master_events = len([c for c in master_cal.walk() if c.name == 'VEVENT'])
        
        return {
            'status': 'success',
            'message': '✅ Sincronização concluída com sucesso!',
            'events_downloaded': len(events),
            'import_count': import_events,
            'master_count': master_events,
            'manual_blocks': len(manual_blocks),
            'manual_removes': len(manual_removes),
            'timestamp': datetime.now().isoformat(),
        }
    
    except Exception as e:
        log_error(f"Sync failed: {e}")
        return {
            'status': 'error',
            'message': str(e),
        }


# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    log_info('=' * 70)
    log_info('CALENDAR SYNCHRONIZATION - v4.0')
    log_info(f'Timestamp: {datetime.now().isoformat()}')
    log_info(f'Config: TP antes={BUFFER_DAYS_BEFORE}d, TP depois={BUFFER_DAYS_AFTER}d')
    log_info(f'REPO_PATH: {REPO_PATH}')
    log_info('=' * 70)
    
    result = sync_local()
    
    if result.get('status') == 'error':
        log_error(f"SYNC FAILED: {result.get('message')}")
        sys.exit(1)
    else:
        log_success('SYNC COMPLETED SUCCESSFULLY')
        print()
        print(f"Events downloaded: {result.get('events_downloaded', 0)}")
        print(f"Import calendar: {result.get('import_count', 0)} events")
        print(f"Master calendar: {result.get('master_count', 0)} events")
        print(f"Manual blocks applied: {result.get('manual_blocks', 0)}")
        print(f"Manual removes applied: {result.get('manual_removes', 0)}")
        print()
        sys.exit(0)
