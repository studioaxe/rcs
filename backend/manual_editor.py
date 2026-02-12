#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
backend/manual_editor.py - Manual Calendar Editor Handler

Versão: 1.0 Final
Data: 02 de fevereiro de 2026
Desenvolvido por: PBrandão
"""

import os
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from icalendar import Calendar, Event
import pytz
import uuid

logger = logging.getLogger(__name__)

# Caminhos relativos ao repositório
REPO_PATH = Path(__file__).parent.parent
IMPORT_CALENDAR_PATH = REPO_PATH / 'import_calendar.ics'
MANUAL_CALENDAR_PATH = REPO_PATH / 'manual_calendar.ics'
PT_TZ = pytz.timezone('Europe/Lisbon')

# COLORMAP - CORRIGIDA v1.2
COLORMAP = {
    'available': '4dd9ff',      # Azul Claro
    'reserved': 'ff0000',        # Vermelho
    'prep-time': 'ffaa00',       # Laranja
    'manual-block': '00ff00',    # Verde Neon ✅ CORRIGIDO
    'manual-remove': 'ffff00',   # Amarelo ✅ CORRIGIDO
}


def convert_categories_to_string(categories):
    """Converte objeto vCategory para string."""
    if not categories:
        return ''
    try:
        if hasattr(categories, 'to_ical'):
            result = categories.to_ical()
            if isinstance(result, bytes):
                return result.decode('utf-8')
            return str(result)
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
                        logger.info(f'Carregados {len(self.manual_events)} eventos do manual_calendar.ics')
                    except Exception as e:
                        logger.error(f'Erro ao fazer parse do ICS: {e}')
                        self.manual_events = []
            else:
                self.manual_events = []
        except Exception as e:
            logger.error(f'Erro ao abrir ficheiro manual_calendar.ics: {e}')
            self.manual_events = []

    def load_import_events(self) -> List[Dict]:
        """Carrega eventos do import_calendar.ics."""
        events = []
        try:
            if not Path(IMPORT_CALENDAR_PATH).exists():
                logger.warning(f'{IMPORT_CALENDAR_PATH} não encontrado')
                return events

            with open(IMPORT_CALENDAR_PATH, 'rb') as f:
                cal = Calendar.from_ical(f.read())
                for component in cal.walk():
                    if component.name != 'VEVENT':
                        continue

                    dtstart = component.get('DTSTART')
                    dtend = component.get('DTEND')
                    categories = component.get('CATEGORIES')
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

            logger.info(f'Carregados {len(events)} eventos do import_calendar.ics')
            return events

        except Exception as e:
            logger.error(f'Erro ao carregar import_calendar.ics: {e}')
            return events

    def load_manual_events(self) -> List[Dict]:
        """Carrega eventos manuais como dicts."""
        events = []
        try:
            for component in self.manual_events:
                dtstart = component.get('DTSTART')
                dtend = component.get('DTEND')
                categories = component.get('CATEGORIES')
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

            logger.info(f'Processados {len(events)} eventos manuais')
            return events

        except Exception as e:
            logger.error(f'Erro ao carregar manual_events: {e}')
            return events

    def process_calendar_data(self, import_events: List[Dict], manual_events: List[Dict]) -> Dict[str, Dict]:
        """Processa eventos e retorna dados formatados para o calendário."""
        calendar_data = {}
        try:
            today = date.today()
            start_date = today - timedelta(days=365) # Look back one year
            end_date = today + timedelta(days=365) # Look forward one year
            logger.info(f'Processando período {start_date} até {end_date}')

            # Inicializar calendário
            current = start_date
            while current <= end_date:
                date_str = current.isoformat()
                calendar_data[date_str] = {
                    'category': 'AVAILABLE',
                    'description': 'Disponível',
                    'uid': '',
                    'color': COLORMAP.get('available', '#4dd9ff')
                }
                current += timedelta(days=1)

            # Unir e ordenar todos os eventos por data de início
            all_events = sorted(import_events + manual_events, key=lambda x: x.get('dtstart') or '9999-12-31')

            # Mapeamento de regras de sobreposição
            # RESERVATION sobrepõe tudo
            # PREP-TIME só sobrepõe AVAILABLE
            # MANUAL-BLOCK sobrepõe tudo
            # MANUAL-REMOVE "limpa" para AVAILABLE
            overlay_priority = {
                'RESERVATION': 3,
                'MANUAL-BLOCK': 3,
                'PREP-TIME': 2,
                'MANUAL-REMOVE': 1,
                'AVAILABLE': 0
            }

            for event in all_events:
                try:
                    dtstart_str = event.get('dtstart')
                    dtend_str = event.get('dtend')
                    category = event.get('categories', '').upper().strip()
                    summary = event.get('summary', 'Evento')
                    uid = event.get('uid', '')

                    if not dtstart_str or not dtend_str:
                        continue

                    dtstart_date = datetime.fromisoformat(dtstart_str.split('T')[0]).date()
                    dtend_date = datetime.fromisoformat(dtend_str.split('T')[0]).date()
                    
                    current = dtstart_date
                    while current < dtend_date:
                        date_str = current.isoformat()
                        if date_str in calendar_data:
                            # Lógica de sobreposição
                            current_category = calendar_data[date_str]['category']
                            
                            if 'MANUAL-REMOVE' in category:
                                calendar_data[date_str]['category'] = 'AVAILABLE'
                                calendar_data[date_str]['description'] = 'Disponível'
                                calendar_data[date_str]['uid'] = ''
                                calendar_data[date_str]['color'] = COLORMAP.get('available')
                            
                            elif 'RESERVATION' in category:
                                calendar_data[date_str]['category'] = 'RESERVATION'
                                calendar_data[date_str]['description'] = summary
                                calendar_data[date_str]['uid'] = uid
                                calendar_data[date_str]['color'] = COLORMAP.get('reserved')

                            elif 'MANUAL-BLOCK' in category:
                                calendar_data[date_str]['category'] = 'MANUAL-BLOCK'
                                calendar_data[date_str]['description'] = summary
                                calendar_data[date_str]['uid'] = uid
                                calendar_data[date_str]['color'] = COLORMAP.get('manual-block')

                            elif 'PREP-TIME' in category and calendar_data[date_str]['category'] == 'AVAILABLE':
                                calendar_data[date_str]['category'] = 'PREP-TIME'
                                calendar_data[date_str]['description'] = summary
                                calendar_data[date_str]['uid'] = uid
                                calendar_data[date_str]['color'] = COLORMAP.get('prep-time')

                        current += timedelta(days=1)

                except Exception as e:
                    logger.warning(f"Erro ao processar evento: {summary} - {e}")
                    continue

            logger.info(f'Processados {len(calendar_data)} dias')
            return calendar_data

        except Exception as e:
            logger.error(f'Erro ao processar dados do calendário: {e}', exc_info=True)
            return {}

    def block_dates(self, dates: List[str]) -> bool:
        """Bloqueia datas (MANUAL-BLOCK).
        
        ✅ V1.3: SUMMARY e DESCRIPTION mostram DTSTART a DTEND (iCalendar)
        """
        try:
            for date_str in dates:
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    logger.error(f'Formato de data inválido: {date_str}')
                    continue

                # Calcular DTEND (exclusivo)
                dtend_obj = date_obj + timedelta(days=1)

                # ✅ V1.3: SUMMARY e DESCRIPTION mostram DTSTART a DTEND
                summary_text = f'Bloqueio Manual de {date_obj.isoformat()} a {dtend_obj.isoformat()}'
                description_text = f'Data Bloqueada Manualmente ({date_obj.isoformat()} a {dtend_obj.isoformat()})'

                # Criar evento MANUAL-BLOCK
                event = Event()
                event.add('uid', f'manual-block-{date_str}-{uuid.uuid4()}')
                event.add('summary', summary_text)
                event.add('description', description_text)
                event.add('dtstart', date_obj)
                event.add('dtend', dtend_obj)
                event.add('categories', 'MANUAL-BLOCK')
                event.add('created', datetime.now(PT_TZ))
                event.add('last-modified', datetime.now(PT_TZ))
                event.add('status', 'CONFIRMED')
                event.add('transp', 'TRANSPARENT')
                event.add('class', 'PUBLIC')

                self.manual_events.append(event)
                logger.info(f'MANUAL-BLOCK: {date_str}')

            logger.info(f'Bloqueadas {len(dates)} datas')
            return True

        except Exception as e:
            logger.error(f'Erro ao bloquear datas: {e}')
            return False

    def block_date_range(self, start_date: str, end_date: str) -> bool:
        """Bloqueia intervalo de datas (MANUAL-BLOCK).
        
        Cria um ÚNICO evento abrangendo todo o intervalo.
        start_date: '2026-02-25' (inclusivo)
        end_date: '2026-02-28' (inclusivo)
        → Evento de DTSTART=20260225 a DTEND=20260301 (01 março = exclusivo)
        → ✅ V1.3: SUMMARY/DESCRIPTION mostram DTSTART a DTEND (iCalendar)
        """
        try:
            try:
                start_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError as e:
                logger.error(f'Formato de data inválido: {start_date} a {end_date}')
                return False

            # DTEND é exclusivo, portanto deve ser o dia APÓS o último dia inclusivo
            dtend_obj = end_obj + timedelta(days=1)

            # ✅ V1.3: SUMMARY e DESCRIPTION mostram datas iCalendar (DTSTART a DTEND)
            summary_text = f'Bloqueio Manual de {start_obj.isoformat()} a {dtend_obj.isoformat()}'
            description_text = f'Data Bloqueada Manualmente ({start_obj.isoformat()} a {dtend_obj.isoformat()})'

            # Criar ÚNICO evento MANUAL-BLOCK para todo o intervalo
            event = Event()
            event.add('uid', f'manual-block-{start_date}-{end_date}-{uuid.uuid4()}')
            event.add('summary', summary_text)
            event.add('description', description_text)
            event.add('dtstart', start_obj)
            event.add('dtend', dtend_obj)
            event.add('categories', 'MANUAL-BLOCK')
            event.add('created', datetime.now(PT_TZ))
            event.add('last-modified', datetime.now(PT_TZ))
            event.add('status', 'CONFIRMED')
            event.add('transp', 'TRANSPARENT')
            event.add('class', 'PUBLIC')

            self.manual_events.append(event)
            logger.info(f'MANUAL-BLOCK (intervalo): {start_date} a {end_date}')
            return True

        except Exception as e:
            logger.error(f'Erro ao bloquear intervalo: {e}')
            return False

    def remove_events(self, dates: List[str]) -> bool:
        """Remove eventos (MANUAL-REMOVE).
        
        ✅ V1.3: SUMMARY e DESCRIPTION mostram DTSTART a DTEND (iCalendar)
        """
        try:
            for date_str in dates:
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    logger.error(f'Formato de data inválido: {date_str}')
                    continue

                # Calcular DTEND (exclusivo)
                dtend_obj = date_obj + timedelta(days=1)

                # ✅ V1.3: SUMMARY e DESCRIPTION mostram DTSTART a DTEND
                summary_text = f'Remoção Manual de {date_obj.isoformat()} a {dtend_obj.isoformat()}'
                description_text = f'Data Desbloqueada Manualmente ({date_obj.isoformat()} a {dtend_obj.isoformat()})'

                # Criar evento MANUAL-REMOVE
                event = Event()
                event.add('uid', f'manual-remove-{date_str}-{uuid.uuid4()}')
                event.add('summary', summary_text)
                event.add('description', description_text)
                event.add('dtstart', date_obj)
                event.add('dtend', dtend_obj)
                event.add('categories', 'MANUAL-REMOVE')
                event.add('created', datetime.now(PT_TZ))
                event.add('last-modified', datetime.now(PT_TZ))
                event.add('status', 'CONFIRMED')
                event.add('transp', 'TRANSPARENT')
                event.add('class', 'PUBLIC')

                self.manual_events.append(event)
                logger.info(f'MANUAL-REMOVE: {date_str}')

            logger.info(f'Removidas {len(dates)} datas')
            return True

        except Exception as e:
            logger.error(f'Erro ao remover eventos: {e}')
            return False

    def remove_event_range(self, start_date: str, end_date: str) -> bool:
        """Remove intervalo de datas (MANUAL-REMOVE).
        
        Cria um ÚNICO evento abrangendo todo o intervalo.
        start_date: '2026-02-25'
        end_date: '2026-02-28'
        → Evento de 25 a 29 (28 é inclusivo, dtend é exclusivo)
        → ✅ V1.3: SUMMARY/DESCRIPTION mostram DTSTART a DTEND (iCalendar)
        """
        try:
            try:
                start_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError as e:
                logger.error(f'Formato de data inválido: {start_date} a {end_date}')
                return False

            # dtend deve ser o dia APÓS o último dia inclusivo
            dtend_obj = end_obj + timedelta(days=1)

            # ✅ V1.3: SUMMARY e DESCRIPTION mostram datas iCalendar (DTSTART a DTEND)
            summary_text = f'Remoção Manual de {start_obj.isoformat()} a {dtend_obj.isoformat()}'
            description_text = f'Data Desbloqueada Manualmente ({start_obj.isoformat()} a {dtend_obj.isoformat()})'

            # Criar ÚNICO evento MANUAL-REMOVE para todo o intervalo
            event = Event()
            event.add('uid', f'manual-remove-{start_date}-{end_date}-{uuid.uuid4()}')
            event.add('summary', summary_text)
            event.add('description', description_text)
            event.add('dtstart', start_obj)
            event.add('dtend', dtend_obj)
            event.add('categories', 'MANUAL-REMOVE')
            event.add('created', datetime.now(PT_TZ))
            event.add('last-modified', datetime.now(PT_TZ))
            event.add('status', 'CONFIRMED')
            event.add('transp', 'TRANSPARENT')
            event.add('class', 'PUBLIC')

            self.manual_events.append(event)
            logger.info(f'MANUAL-REMOVE (intervalo): {start_date} a {end_date}')
            return True

        except Exception as e:
            logger.error(f'Erro ao remover intervalo: {e}')
            return False

    def clear_events(self, dates: List[str]) -> bool:
        """Limpa eventos de datas especificadas.
        
        ✅ NOVO v1.2: Lógica simplificada
        - Remove do manual_calendar.ics
        - Backend cuida do fallback ao merge
        """
        try:
            for date_str in dates:
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    logger.error(f'Formato de data inválido: {date_str}')
                    continue

                # Remover eventos dessa data do manual_events
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
                        else:
                            new_events.append(event)
                    except:
                        new_events.append(event)

                self.manual_events = new_events
                logger.info(f'CLEAR: {date_str}')

            logger.info(f'Limpas {len(dates)} datas')
            return True

        except Exception as e:
            logger.error(f'Erro ao limpar eventos: {e}')
            return False

    def save_manual_calendar(self) -> bool:
        """Guarda manual_calendar.ics no disco local.
        
        ✅ CORRIGIDO v1.1: Modo binário correto (wb + bytes)
        """
        try:
            # Criar calendário iCalendar
            cal = Calendar()
            cal.add('prodid', '-//Rental Manual Calendar//PT')
            cal.add('version', '2.0')
            cal.add('calscale', 'GREGORIAN')
            cal.add('x-wr-calname', 'Manual Calendar')
            cal.add('x-wr-timezone', 'Europe/Lisbon')

            # Adicionar todos os eventos manuais
            for event in self.manual_events:
                cal.add_component(event)

            # ✅ CORREÇÃO CRÍTICA: to_ical() retorna bytes, escrever diretamente
            ical_bytes = cal.to_ical()

            # Escrever no disco em modo binário
            with open(MANUAL_CALENDAR_PATH, 'wb') as f:
                f.write(ical_bytes)

            logger.info(f'✅ Guardado {MANUAL_CALENDAR_PATH} com {len(self.manual_events)} eventos')
            return True

        except Exception as e:
            logger.error(f'❌ Erro ao guardar manual_calendar.ics: {e}', exc_info=True)
            return False


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    handler = ManualEditorHandler()
    import_events = handler.load_import_events()
    manual_events = handler.load_manual_events()
    calendar_data = handler.process_calendar_data(import_events, manual_events)

    print(f'Processados {len(calendar_data)} dias')
    print('Primeiros 5 dias:')
    for i, (date_str, data) in enumerate(sorted(calendar_data.items())[:5]):
        print(f'  {date_str}: {data["category"]}')
