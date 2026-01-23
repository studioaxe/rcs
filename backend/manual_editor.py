#!/usr/bin/env python3

# backend/manual_editor.py - Manual Editor Handler
# Versão 1.1 - CORRIGIDO - Conversão vCategory

import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from icalendar import Calendar, Event
import pytz
import uuid

logger = logging.getLogger(__name__)

# Paths
REPO_PATH = Path(__file__).parent.parent
IMPORT_CALENDAR_PATH = REPO_PATH / "import_calendar.ics"
MANUAL_CALENDAR_PATH = REPO_PATH / "manual_calendar.ics"

# Timezone
PT_TZ = pytz.timezone('Europe/Lisbon')

# 🔥 MAPA DE CORES
COLOR_MAP = {
    'available': '#4dd9ff',
    'reserved': '#ff0000',
    'prep-time': '#ffaa00',
    'blocked': '#0000ff',
    'removed': '#ffff00',
}


def convert_categories_to_string(categories):
    """Converte objeto vCategory para string."""
    if not categories:
        return ''
    
    try:
        # Se tem método to_ical(), usar
        if hasattr(categories, 'to_ical'):
            result = categories.to_ical()
            if isinstance(result, bytes):
                return result.decode('utf-8')
            return str(result)
        
        # Senão, converter directamente
        result = str(categories)
        return result
    except:
        return ''


class ManualEditorHandler:
    """Handler para operações do editor manual de calendário."""

    def __init__(self):
        """Inicializa o handler."""
        self.manual_events = []
        self.load_manual_events_into_memory()

    def load_manual_events_into_memory(self):
        """Carrega eventos manuais em memória."""
        try:
            if Path(MANUAL_CALENDAR_PATH).exists():
                with open(MANUAL_CALENDAR_PATH, 'rb') as f:
                    try:
                        cal = Calendar.from_ical(f.read())
                        for component in cal.walk():
                            if component.name == 'VEVENT':
                                self.manual_events.append(component)
                        logger.info(f"Carregados {len(self.manual_events)} eventos do manual_calendar.ics")
                    except Exception as e:
                        logger.error(f"Erro ao fazer parse do ICS: {e}")
                        self.manual_events = []
            else:
                self.manual_events = []
        except Exception as e:
            logger.error(f"Erro ao abrir ficheiro manual_calendar.ics: {e}")
            self.manual_events = []

    def load_import_events(self) -> List[Dict]:
        """Carrega eventos do import_calendar.ics."""
        events = []
        try:
            if not Path(IMPORT_CALENDAR_PATH).exists():
                logger.warning(f"{IMPORT_CALENDAR_PATH} não encontrado")
                return events

            with open(IMPORT_CALENDAR_PATH, 'rb') as f:
                cal = Calendar.from_ical(f.read())
                for component in cal.walk():
                    if component.name != 'VEVENT':
                        continue

                    dtstart = component.get('DTSTART')
                    dtend = component.get('DTEND')
                    categories = component.get('CATEGORIES')

                    # ✅ CONVERTER vCategory PARA STRING
                    categories_str = convert_categories_to_string(categories)

                    event = {
                        'uid': str(component.get('UID', '')),
                        'summary': str(component.get('SUMMARY', '')),
                        'dtstart': dtstart.dt.isoformat() if dtstart else None,
                        'dtend': dtend.dt.isoformat() if dtend else None,
                        'description': str(component.get('DESCRIPTION', '')),
                        'categories': categories_str,
                    }

                    events.append(event)

            logger.info(f"Carregados {len(events)} eventos do import_calendar.ics")
            return events

        except Exception as e:
            logger.error(f"Erro ao carregar import_calendar.ics: {e}")
            return events

    def load_manual_events(self) -> List[Dict]:
        """Carrega eventos manuais como dicts."""
        events = []
        try:
            for component in self.manual_events:
                dtstart = component.get('DTSTART')
                dtend = component.get('DTEND')
                categories = component.get('CATEGORIES')

                # ✅ CONVERTER vCategory PARA STRING
                categories_str = convert_categories_to_string(categories)

                dtstart_value = None
                dtend_value = None

                if dtstart:
                    try:
                        dtstart_value = dtstart.dt.isoformat()
                    except:
                        dtstart_value = str(dtstart.dt)

                if dtend:
                    try:
                        dtend_value = dtend.dt.isoformat()
                    except:
                        dtend_value = str(dtend.dt)

                event = {
                    'uid': str(component.get('UID', '')),
                    'summary': str(component.get('SUMMARY', '')),
                    'dtstart': dtstart_value,
                    'dtend': dtend_value,
                    'description': str(component.get('DESCRIPTION', '')),
                    'categories': categories_str,
                }

                events.append(event)

            logger.info(f"Processados {len(events)} eventos manuais")
            return events

        except Exception as e:
            logger.error(f"Erro ao carregar manual_events: {e}")
            return events

    def process_calendar_data(self, import_events: List[Dict], manual_events: List[Dict]) -> Dict[str, Dict]:
        """
        Processa eventos e retorna dados formatados para o calendário.
        """
        calendar_data = {}

        try:
            today = date.today()
            start_date = today
            end_date = today + timedelta(days=90)

            logger.info(f"Processando período {start_date} até {end_date} (90 dias)")

            current = start_date
            while current <= end_date:
                date_str = current.isoformat()
                calendar_data[date_str] = {
                    'category': 'available',
                    'descriptions': [],
                    'color': COLOR_MAP['available']
                }
                current += timedelta(days=1)

            # ========================================================================
            # PROCESSAR EVENTOS DE IMPORTAÇÃO
            # ========================================================================

            for event in import_events:
                try:
                    dtstart_str = event.get('dtstart')
                    dtend_str = event.get('dtend')
                    categories = (event.get('categories') or '').upper()
                    summary = event.get('summary', 'Evento')

                    if not dtstart_str:
                        continue

                    # Parse data de início
                    if 'T' in dtstart_str:
                        dtstart_date = datetime.fromisoformat(dtstart_str.split('T')[0]).date()
                    else:
                        dtstart_date = datetime.fromisoformat(dtstart_str).date()

                    # Parse data de fim
                    if dtend_str:
                        if 'T' in dtend_str:
                            dtend_date = datetime.fromisoformat(dtend_str.split('T')[0]).date()
                        else:
                            dtend_date = datetime.fromisoformat(dtend_str).date()
                    else:
                        dtend_date = dtstart_date

                    # Aplicar categoria a todos os dias do evento
                    current = dtstart_date
                    while current <= dtend_date:
                        date_str = current.isoformat()

                        if date_str in calendar_data:
                            # LÓGICA DE PRIORIDADE: RESERVED > PREP-TIME > AVAILABLE
                            if 'RESERVATION' in categories:
                                calendar_data[date_str]['category'] = 'reserved'
                                calendar_data[date_str]['color'] = COLOR_MAP['reserved']
                            elif 'PREP-TIME' in categories:
                                if calendar_data[date_str]['category'] == 'available':
                                    calendar_data[date_str]['category'] = 'prep-time'
                                    calendar_data[date_str]['color'] = COLOR_MAP['prep-time']

                            # Adicionar descrição
                            if summary not in calendar_data[date_str]['descriptions']:
                                calendar_data[date_str]['descriptions'].append(summary)

                        current += timedelta(days=1)

                except Exception as e:
                    logger.warning(f"Erro ao processar evento de importação: {e}")
                    continue

            # ========================================================================
            # PROCESSAR EVENTOS MANUAIS
            # ========================================================================

            for event in manual_events:
                try:
                    dtstart_str = event.get('dtstart')
                    dtend_str = event.get('dtend')
                    categories = (event.get('categories') or '').upper()
                    summary = event.get('summary', 'Evento Manual')

                    if not dtstart_str:
                        continue

                    # Parse data de início
                    if 'T' in dtstart_str:
                        dtstart_date = datetime.fromisoformat(dtstart_str.split('T')[0]).date()
                    else:
                        dtstart_date = datetime.fromisoformat(dtstart_str).date()

                    # Parse data de fim
                    if dtend_str:
                        if 'T' in dtend_str:
                            dtend_date = datetime.fromisoformat(dtend_str.split('T')[0]).date()
                        else:
                            dtend_date = datetime.fromisoformat(dtend_str).date()
                    else:
                        dtend_date = dtstart_date

                    # Aplicar categoria manual
                    current = dtstart_date
                    while current <= dtend_date:
                        date_str = current.isoformat()

                        if date_str in calendar_data:
                            if 'MANUAL-BLOCK' in categories:
                                calendar_data[date_str]['category'] = 'blocked'
                                calendar_data[date_str]['color'] = COLOR_MAP['blocked']
                            elif 'MANUAL-REMOVE' in categories:
                                calendar_data[date_str]['category'] = 'removed'
                                calendar_data[date_str]['color'] = COLOR_MAP['removed']

                        current += timedelta(days=1)

                except Exception as e:
                    logger.warning(f"Erro ao processar evento manual: {e}")
                    continue

            logger.info(f"Processados {len(calendar_data)} dias")
            return calendar_data

        except Exception as e:
            logger.error(f"Erro ao processar dados do calendário: {e}", exc_info=True)
            return {}

    def block_dates(self, dates: List[str]) -> bool:
        """Bloqueia datas (MANUAL-BLOCK)."""
        try:
            for date_str in dates:
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    logger.error(f"Formato de data inválido: {date_str}")
                    continue

                event = Event()
                event.add('uid', f"manual-block-{date_str}-{uuid.uuid4()}")
                event.add('summary', date_str)
                event.add('description', 'Data Bloqueada Manualmente')
                event.add('dtstart', date_obj)
                event.add('dtend', date_obj + timedelta(days=1))
                event.add('categories', 'MANUAL-BLOCK')
                event.add('created', datetime.now(PT_TZ))
                event.add('last-modified', datetime.now(PT_TZ))
                event.add('status', 'CONFIRMED')
                event.add('transp', 'TRANSPARENT')
                event.add('class', 'PUBLIC')

                self.manual_events.append(event)
                logger.info(f"MANUAL-BLOCK: {date_str}")

            logger.info(f"Bloqueadas {len(dates)} datas")
            return True

        except Exception as e:
            logger.error(f"Erro ao bloquear datas: {e}")
            return False

    def remove_events(self, dates: List[str]) -> bool:
        """Remove eventos (MANUAL-REMOVE)."""
        try:
            for date_str in dates:
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    logger.error(f"Formato de data inválido: {date_str}")
                    continue

                event = Event()
                event.add('uid', f"manual-remove-{date_str}-{uuid.uuid4()}")
                event.add('summary', date_str)
                event.add('description', 'Data Desbloqueada Manualmente')
                event.add('dtstart', date_obj)
                event.add('dtend', date_obj + timedelta(days=1))
                event.add('categories', 'MANUAL-REMOVE')
                event.add('created', datetime.now(PT_TZ))
                event.add('last-modified', datetime.now(PT_TZ))
                event.add('status', 'CONFIRMED')
                event.add('transp', 'TRANSPARENT')
                event.add('class', 'PUBLIC')

                self.manual_events.append(event)
                logger.info(f"MANUAL-REMOVE: {date_str}")

            logger.info(f"Removidas {len(dates)} datas")
            return True

        except Exception as e:
            logger.error(f"Erro ao remover eventos: {e}")
            return False

    def clear_events(self, dates: List[str]) -> bool:
        """Limpa eventos de datas especificadas."""
        try:
            for date_str in dates:
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    logger.error(f"Formato de data inválido: {date_str}")
                    continue

                new_events = []
                for event in self.manual_events:
                    try:
                        event_date = event.get('DTSTART')
                        if event_date:
                            event_date = event_date.dt
                            if isinstance(event_date, datetime):
                                event_date = event_date.date()

                            if event_date != date_obj:
                                new_events.append(event)
                    except:
                        new_events.append(event)

                self.manual_events = new_events
                logger.info(f"CLEAR: {date_str}")

            logger.info(f"Limpas {len(dates)} datas")
            return True

        except Exception as e:
            logger.error(f"Erro ao limpar eventos: {e}")
            return False

    def save_manual_calendar(self) -> bool:
        """Guarda manual_calendar.ics."""
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
            ical_data = ical_data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')

            with open(MANUAL_CALENDAR_PATH, 'wb') as f:
                f.write(ical_data)

            logger.info(f"Guardado {MANUAL_CALENDAR_PATH} com {len(self.manual_events)} eventos")
            return True

        except Exception as e:
            logger.error(f"Erro ao guardar manual_calendar.ics: {e}")
            return False


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    handler = ManualEditorHandler()
    import_events = handler.load_import_events()
    manual_events = handler.load_manual_events()
    calendar_data = handler.process_calendar_data(import_events, manual_events)

    print(f"Processados {len(calendar_data)} dias")
    print("Primeiros 5 dias:")
    for i, (date, data) in enumerate(sorted(calendar_data.items())[:5]):
        print(f"  {date}: {data['category']}")
