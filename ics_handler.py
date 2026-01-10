"""
ics_handler.py - Leitura, escrita e criação de ficheiros ICS
"""

from datetime import datetime, date
from typing import List, Dict, Optional

from icalendar import Calendar, Event
import pytz

from config import get_config

cfg = get_config()
PT_TZ = pytz.timezone('Europe/Lisbon')


def to_datetime(dt_obj: Optional[object]) -> Optional[datetime]:
    """Converte date/datetime em datetime com timezone UTC."""
    if dt_obj is None:
        return None
    if isinstance(dt_obj, datetime):
        if dt_obj.tzinfo is None:
            return dt_obj.replace(tzinfo=pytz.UTC)
        return dt_obj
    if isinstance(dt_obj, date):
        return datetime.combine(dt_obj, datetime.min.time()).replace(tzinfo=pytz.UTC)
    return None


class ICSHandler:
    """Handler para ficheiros ICS (import, master, manual)."""

    @staticmethod
    def read_ics_file(filepath: str) -> Optional[List[Dict]]:
        """Lê um ficheiro ICS e devolve lista de eventos em dicts."""
        try:
            from pathlib import Path
            if not Path(filepath).is_file():
                return None

            with open(filepath, 'rb') as f:
                cal = Calendar.from_ical(f.read())

            events = []
            for component in cal.walk():
                if component.name != "VEVENT":
                    continue

                ev = {
                    'uid': str(component.get('uid', '')),
                    'summary': str(component.get('summary', '')),
                    'dtstart': component.get('dtstart'),
                    'dtend': component.get('dtend'),
                    'description': str(component.get('description', '')),
                    'categories': str(component.get('categories', '')),
                    'status': str(component.get('status', 'CONFIRMED'))
                }

                if ev['dtstart']:
                    dt = ev['dtstart'].dt
                    ev['dtstart'] = dt.isoformat() if hasattr(dt, 'isoformat') else str(dt)
                if ev['dtend']:
                    dt = ev['dtend'].dt
                    ev['dtend'] = dt.isoformat() if hasattr(dt, 'isoformat') else str(dt)

                events.append(ev)

            return events

        except Exception:
            return None

    @staticmethod
    def save_ics_file(filepath: str, events: List[Dict]) -> bool:
        """Guarda lista de eventos (dict) num ficheiro ICS."""
        try:
            cal = Calendar()
            cal.add('prodid', '-//Rental Calendar Sync//PT')
            cal.add('version', '2.0')
            cal.add('calscale', 'GREGORIAN')
            cal.add('x-wr-calname', 'Rental Calendar')
            cal.add('x-wr-timezone', 'Europe/Lisbon')

            for ev in events:
                e = Event()
                e.add('summary', ev.get('summary', 'Event'))

                dtstart = ev.get('dtstart')
                dtend = ev.get('dtend')
                if dtstart:
                    e.add('dtstart', dtstart)
                if dtend:
                    e.add('dtend', dtend)

                e.add('uid', ev.get('uid', ''))
                e.add('description', ev.get('description', ''))
                if ev.get('categories'):
                    e.add('categories', ev.get('categories'))
                e.add('status', ev.get('status', 'CONFIRMED'))
                e.add('created', datetime.now(PT_TZ))

                cal.add_component(e)

            with open(filepath, 'wb') as f:
                f.write(cal.to_ical())
            return True

        except Exception:
            return False
