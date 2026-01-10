"""
sync_engine.py - Wrapper para reutilizar lógica de sync_calendars.py
Usado pela API da Render quando quiseres sync local (não GitHub).
"""

import sys
from typing import Dict, Any
from pathlib import Path

# Adicionar scripts/ ao Python path (onde está o sync_calendars.py)
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from config import get_config
from ics_handler import ICSHandler

# Importa as funções do script batch existente
from sync_calendars import (  # type: ignore
    fetch_all_calendars,
    extract_events,
    deduplicate_events,
    create_import_calendar,
    create_master_calendar,
    export_to_file,
    MANUAL_CALENDAR_PATH,
    IMPORT_CALENDAR_PATH,
    MASTER_CALENDAR_PATH,
)

cfg = get_config()


def sync_local() -> Dict[str, Any]:
    """
    Executa o mesmo pipeline do sync_calendars.py, mas chamado via Flask.
    Gera import_calendar.ics e master_calendar.ics.
    """
    try:
        calendars = fetch_all_calendars()
        if calendars is None:
            return {
                "status": "error",
                "message": "Nenhum calendário importado com sucesso",
            }

        events = extract_events(calendars)
        if not events:
            return {"status": "error", "message": "Nenhum evento encontrado"}

        events = deduplicate_events(events)

        manual_cal = None
        blocked_uids = set()
        if Path(MANUAL_CALENDAR_PATH).is_file():
            from sync_calendars import load_manual_calendar, get_blocked_uids  # type: ignore

            manual_cal = load_manual_calendar()
            blocked_uids = get_blocked_uids(manual_cal)

        import_cal = create_import_calendar(events)
        master_cal = create_master_calendar(import_cal, blocked_uids)

        if not export_to_file(import_cal, IMPORT_CALENDAR_PATH):
            return {
                "status": "error",
                "message": "Falha ao gravar import_calendar.ics",
            }

        if not export_to_file(master_cal, MASTER_CALENDAR_PATH):
            return {
                "status": "error",
                "message": "Falha ao gravar master_calendar.ics",
            }

        # Contagens rápidas
        import_events = ICSHandler.read_ics_file(IMPORT_CALENDAR_PATH) or []
        master_events = ICSHandler.read_ics_file(MASTER_CALENDAR_PATH) or []

        return {
            "status": "success",
            "events_downloaded": len(events),
            "import_count": len(import_events),
            "master_count": len(master_events),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
