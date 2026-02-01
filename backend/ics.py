#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
backend/ics.py - Handler para Ficheiros ICS

Versão: 1.0 Final
Data: 01 de fevereiro de 2026
Desenvolvido por: PBrandão

Operações com ficheiros ICS (iCalendar):

1. read_ics_file(filepath) - Ler ficheiros locais
2. parse(ics_content_string) - Parse de strings ICS (GitHub/API)
3. save_ics_file(filepath, events) - Guardar ficheiros
4. get_event_by_uid(events, uid) - Procurar evento por UID
5. filter_by_category(events, category) - Filtrar por categoria
6. count_events_by_category(events) - Contar por categoria

Funcionalidades:
- Leitura e escrita de ficheiros .ics com parsing correcto
- Parse de conteúdo ICS em bruto (para GitHub raw content)
- Serialização JSON-compatível para categories
- Suporte a timezone Europe/Lisbon
- Logging completo para debugging
- Validação robusta de entrada
"""

import os
import logging
from datetime import datetime, date
from typing import List, Dict, Optional
from pathlib import Path
from icalendar import Calendar, Event
import pytz

# ============================================================================
# LOGGING SETUP
# ============================================================================

logger = logging.getLogger(__name__)

# ============================================================================
# TIMEZONE CONFIGURATION
# ============================================================================

PT_TZ = pytz.timezone("Europe/Lisbon")

# ============================================================================
# HELPERS - DATA CONVERSION
# ============================================================================


def to_datetime(dtobj: Optional[object]) -> Optional[datetime]:
    """Converte date/datetime em datetime com timezone UTC."""
    if dtobj is None:
        return None
    if isinstance(dtobj, datetime):
        if dtobj.tzinfo is None:
            return dtobj.replace(tzinfo=pytz.UTC)
        return dtobj
    if isinstance(dtobj, date):
        return datetime.combine(dtobj, datetime.min.time()).replace(
            tzinfo=pytz.UTC
        )
    return None


def _serialize_categories(categories) -> str:
    """Converte vCategory (objeto icalendar) → string JSON-serializable.
    
    Categories pode vir em diferentes formatos:
    - None (não existe)
    - String (já processada)
    - vCategory (objeto icalendar)
    """
    if not categories:
        return ""

    if isinstance(categories, str):
        return categories

    # vCategory ou outro objeto → extrair valor
    try:
        # Se tem método to_ical(), usar esse
        if hasattr(categories, 'to_ical'):
            value = categories.to_ical()
            if isinstance(value, bytes):
                return value.decode('utf-8')
            return str(value)
        
        # Se é uma lista, juntar com vírgula
        if isinstance(categories, (list, tuple)):
            return ','.join(str(c) for c in categories)
        
        # Fallback: tentar extrair o atributo 'cats' ou similar
        if hasattr(categories, 'cats'):
            return str(categories.cats)
        
        # Última opção: str()
        return str(categories)
    except Exception:
        logger.debug(f"Failed to serialize categories: {categories}")
        return ""



def _extract_date_iso(dt_component) -> str:
    """Extrai data em formato ISO-8601 de componente vDDDTypes.
    
    Usado por read_ics_file() e parse() para conversão consistente.
    """
    if not dt_component:
        return ""

    try:
        # Se tem atributo 'dt', use isso (vDDDTypes)
        if hasattr(dt_component, "dt"):
            dt_obj = dt_component.dt
        else:
            dt_obj = dt_component

        # Se tem método isoformat, use-o
        if hasattr(dt_obj, "isoformat"):
            return dt_obj.isoformat()

        # Fallback para string
        return str(dt_obj)

    except Exception as e:
        logger.debug(f"Error extracting date: {e}")
        return ""


# ============================================================================
# ICS HANDLER CLASS
# ============================================================================


class ICSHandler:
    """Handler para ficheiros ICS - import, master, manual calendars."""

    @staticmethod
    def read_ics_file(filepath: str) -> Optional[List[Dict]]:
        """
        Lê um ficheiro ICS e devolve lista de eventos em dicts.

        Usa formato ISO-8601 para datas (compatível com JSON).

        Args:
            filepath: Caminho para ficheiro .ics

        Returns:
            Lista de eventos como dicts, ou None se erro ou ficheiro não existe

        Example:
            events = ICSHandler.read_ics_file('master_calendar.ics')
            if events:
                for event in events:
                    print(f"{event['summary']}: {event['dtstart']}")
        """
        try:
            if not Path(filepath).is_file():
                logger.warning(f"ICS file not found: {filepath}")
                return None

            with open(filepath, "rb") as f:
                cal = Calendar.from_ical(f.read())

            events: List[Dict] = []

            for component in cal.walk():
                if component.name != "VEVENT":
                    continue

                # Processar datas como em parse() para consistência
                dtstart = component.get("DTSTART")
                dtend = component.get("DTEND")

                dtstart_str = _extract_date_iso(dtstart)
                dtend_str = _extract_date_iso(dtend)

                ev = {
                    "uid": str(component.get("UID", "")),
                    "summary": str(component.get("SUMMARY", "")),
                    "dtstart": dtstart_str,
                    "dtend": dtend_str,
                    "description": str(component.get("DESCRIPTION", "")),
                    "categories": _serialize_categories(
                        component.get("CATEGORIES", "")
                    ),
                    "status": str(component.get("STATUS", "CONFIRMED")),
                    "location": str(component.get("LOCATION", "")),
                }

                events.append(ev)

            logger.info(f"✅ Loaded {len(events)} events from {filepath}")
            return events if events else None

        except Exception as e:
            logger.error(f"Error reading ICS file {filepath}: {e}")
            return None

    @staticmethod
    def parse(ics_content: str) -> Optional[List[Dict]]:
        """
        Parse de string com conteúdo ICS (não filepath).

        Usado para processar conteúdo direto do GitHub raw ou via requests.

        Usa formato ISO-8601 para datas (compatível com JSON).

        Args:
            ics_content: String com conteúdo ICS completo

        Returns:
            Lista de eventos como dicts, ou None se erro

        Example:
            import requests
            response = requests.get('https://raw.githubusercontent.com/.../file.ics')
            events = ICSHandler.parse(response.text)
        """
        try:
            cal = Calendar.from_ical(ics_content)
            events: List[Dict] = []

            for component in cal.walk():
                if component.name != "VEVENT":
                    continue

                # Processar datas
                dtstart = component.get("DTSTART")
                dtend = component.get("DTEND")

                dtstart_str = _extract_date_iso(dtstart)
                dtend_str = _extract_date_iso(dtend)

                ev = {
                    "uid": str(component.get("UID", "")),
                    "summary": str(component.get("SUMMARY", "")),
                    "dtstart": dtstart_str,
                    "dtend": dtend_str,
                    "description": str(component.get("DESCRIPTION", "")),
                    "categories": _serialize_categories(
                        component.get("CATEGORIES", "")
                    ),
                    "status": str(component.get("STATUS", "CONFIRMED")),
                    "location": str(component.get("LOCATION", "")),
                }

                events.append(ev)

            logger.info(f"✅ Parsed {len(events)} events from ICS string")
            return events if events else None

        except Exception as e:
            logger.error(f"Error parsing ICS content: {e}")
            return None

    @staticmethod
    def save_ics_file(filepath: str, events: List[Dict]) -> bool:
        """
        Guarda lista de eventos dict num ficheiro ICS.

        Cria o directório automaticamente se não existe.

        Args:
            filepath: Caminho de destino do ficheiro .ics
            events: Lista de dicts com dados de eventos

        Returns:
            True se sucesso, False se erro

        Example:
            events = [
                {
                    'uid': '123',
                    'summary': 'Reunião',
                    'dtstart': '2026-01-15',
                    'dtend': '2026-01-16',
                    'description': 'Meeting agenda',
                }
            ]
            success = ICSHandler.save_ics_file('calendar.ics', events)
        """
        try:
            # Criar directório se não existe
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            cal = Calendar()
            cal.add("prodid", "-//Rental Calendar Sync//PT")
            cal.add("version", "2.0")
            cal.add("calscale", "GREGORIAN")
            cal.add("x-wr-calname", "Rental Calendar")
            cal.add("x-wr-timezone", "Europe/Lisbon")

            for ev in events:
                e = Event()
                e.add("summary", ev.get("summary", "Event"))

                dtstart = ev.get("dtstart")
                dtend = ev.get("dtend")

                if dtstart:
                    e.add("dtstart", dtstart)
                if dtend:
                    e.add("dtend", dtend)

                e.add("uid", ev.get("uid", f"event-{datetime.now().timestamp()}"))
                e.add("description", ev.get("description", ""))
                e.add("location", ev.get("location", ""))

                if ev.get("categories"):
                    e.add("categories", ev.get("categories"))

                e.add("status", ev.get("status", "CONFIRMED"))
                e.add("created", datetime.now(PT_TZ))
                e.add("last-modified", datetime.now(PT_TZ))

                cal.add_component(e)

            with open(filepath, "wb") as f:
                f.write(cal.to_ical())

            file_size = os.path.getsize(filepath)
            logger.info(
                f"✅ Saved {len(events)} events to {filepath} ({file_size} bytes)"
            )
            return True

        except Exception as e:
            logger.error(f"Error saving ICS file {filepath}: {e}")
            return False

    @staticmethod
    def get_event_by_uid(events: List[Dict], uid: str) -> Optional[Dict]:
        """
        Procura um evento por UID na lista (case-sensitive).

        Args:
            events: Lista de eventos (output de read_ics_file ou parse)
            uid: UID a procurar

        Returns:
            Dict do evento se encontrado, None caso contrário

        Example:
            event = ICSHandler.get_event_by_uid(events, 'my-event-123')
            if event:
                print(f"Found: {event['summary']}")
        """
        if not events:
            logger.debug("No events to search")
            return None

        if not uid:
            logger.warning("Empty UID search")
            return None

        for event in events:
            if event.get("uid") == uid:
                logger.debug(f"Found event with UID: {uid}")
                return event

        logger.debug(f"Event not found with UID: {uid}")
        return None

    @staticmethod
    def filter_by_category(events: List[Dict], category: str) -> List[Dict]:
        """
        Filtra eventos por categoria (case-insensitive).

        Args:
            events: Lista de eventos
            category: Categoria a procurar (ex: 'MANUAL-BLOCK', 'manual-block')

        Returns:
            Lista de eventos que contêm a categoria

        Example:
            blocks = ICSHandler.filter_by_category(events, 'MANUAL-BLOCK')
            print(f"Found {len(blocks)} blocked dates")
        """
        if not events:
            logger.debug("No events to filter")
            return []

        if not category:
            logger.warning("Empty category filter")
            return []

        category_upper = category.upper()
        filtered = [
            e
            for e in events
            if category_upper in str(e.get("categories", "")).upper()
        ]

        logger.debug(f"Filtered {len(filtered)} events by category '{category}'")
        return filtered

    @staticmethod
    def count_events_by_category(events: List[Dict]) -> Dict[str, int]:
        """
        Conta eventos por categoria.

        Suporta múltiplas categorias por evento (separadas por vírgula).

        Args:
            events: Lista de eventos (output de read_ics_file ou parse)

        Returns:
            Dict com contagem por categoria

        Example:
            counts = ICSHandler.count_events_by_category(events)
            # Output: {'RESERVATION-NATIVE': 5, 'PREP-TIME-BEFORE': 5, 'PREP-TIME-AFTER': 5}
            for cat, count in counts.items():
                print(f"{cat}: {count}")
        """
        if not events:
            logger.debug("No events to count")
            return {}

        counts: Dict[str, int] = {}

        for event in events:
            categories_str = str(event.get("categories", ""))

            if categories_str:
                # Suporta múltiplas categorias separadas por vírgula
                for cat in categories_str.split(","):
                    cat = cat.strip()
                    if cat:
                        counts[cat] = counts.get(cat, 0) + 1

        logger.debug(f"Category counts: {counts}")
        return counts
