#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
backend/manual_editor_endpoints.py

Endpoints Flask para o Editor Manual de Calendário.

Funcionalidades:
- GET  /manual-editor           → Renderiza página HTML do editor
- GET  /api/manual/load         → Carrega import_calendar + manual_calendar para o editor
- POST /api/manual/save         → Grava manual_calendar.ics e regenera master_calendar.ics
- POST /api/full-auto/sync-trigger → Dispara workflow full_auto_workflow.yml no GitHub

Desenvolvido por: PBrandão
Data: 13 de Janeiro de 2026
"""

import subprocess
import requests
from datetime import datetime
from pathlib import Path
from flask import jsonify, render_template_string, session, request
from functools import wraps

# Espera-se que, em main.py, passes um objeto cfg com:
# cfg.REPO_PATH
# cfg.IMPORT_CALENDAR_PATH
# cfg.MANUAL_CALENDAR_PATH
# cfg.MASTER_CALENDAR_PATH
# cfg.GITHUB_TOKEN
# cfg.GITHUB_REPO
# cfg.GITHUB_BRANCH


def api_login_required(f):
    """Decorador para proteger endpoints da API."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session:
            return jsonify(status="error", message="Não autenticado"), 401
        return f(*args, **kwargs)
    return decorated_function


def register_manual_editor_endpoints(app, cfg, logger):
    """
    Regista todos os endpoints do editor manual.

    Chamar em main.py:
        from backend.manual_editor_endpoints import register_manual_editor_endpoints
        register_manual_editor_endpoints(app, cfg, logger)
    """

    # ----------------------------------------------------------------------
    # RENDERIZAR PÁGINA DO EDITOR
    # ----------------------------------------------------------------------
    @app.route("/manual-editor", methods=["GET"])
    def manual_editor_page():
        """Renderiza página HTML do editor manual."""
        try:
            # No teu projeto actual, o HTML está em static/manual_calendar.html
            with open("static/manual_calendar.html", "r", encoding="utf-8") as f:
                html_content = f.read()
            return render_template_string(html_content)
        except FileNotFoundError:
            return render_template_string(
                """
                <html>
                  <head><title>Erro</title></head>
                  <body>
                    <h1>Erro 404</h1>
                    <p>Ficheiro static/manual_calendar.html não encontrado.</p>
                  </body>
                </html>
                """
            ), 404

    # ----------------------------------------------------------------------
    # CARREGAR CALENDÁRIOS PARA O EDITOR
    # ----------------------------------------------------------------------
    @app.route("/api/manual/load", methods=["GET"])
    @api_login_required
    def api_manual_load():
        """
        Carrega eventos para o editor manual.

        Processo:
        1. Gera novo import_calendar.ics (reservas nativas + TPs) via sync_local()
        2. Carrega manual_calendar.ics (eventos manuais existentes)
        3. Devolve estrutura de eventos combinada em JSON
        """
        try:
            from backend.sync import sync_local
            from backend.ics import ICSHandler

            logger.info("[MANUAL EDITOR] Iniciando carregamento de calendários...")

            # 1. Gerar novo import_calendar.ics
            logger.info("[MANUAL EDITOR] Gerando novo import_calendar.ics...")
            sync_result = sync_local()
            if sync_result.get("status") == "error":
                logger.warning(
                    "[MANUAL EDITOR] Erro ao gerar import: %s",
                    sync_result.get("message"),
                )

            # 2. Ler import_calendar.ics
            import_events = []
            try:
                import_events = ICSHandler.read_ics_file(cfg.IMPORT_CALENDAR_PATH) or []
                logger.info(
                    "[MANUAL EDITOR] Carregados %d eventos de import_calendar.ics",
                    len(import_events),
                )
            except Exception as e:
                logger.warning("[MANUAL EDITOR] Erro ao ler import_calendar: %s", e)

            # 3. Ler manual_calendar.ics
            manual_events = []
            try:
                manual_events = ICSHandler.read_ics_file(cfg.MANUAL_CALENDAR_PATH) or []
                logger.info(
                    "[MANUAL EDITOR] Carregados %d eventos de manual_calendar.ics",
                    len(manual_events),
                )
            except Exception as e:
                logger.warning("[MANUAL EDITOR] Erro ao ler manual_calendar: %s", e)

            # 4. Combinar e estruturar eventos
            all_events = []

            def map_color(categories: str) -> str:
                """Mapear CATEGORIES para cor."""
                if not categories:
                    return "lightblue"
                cu = str(categories).upper()
                if "MANUAL-REMOVE" in cu:
                    return "yellow"
                if "MANUAL-BLOCK" in cu:
                    return "lime"
                if "PREP-TIME-BEFORE" in cu or "PREP-TIME-AFTER" in cu:
                    return "orange"
                if "RESERVATION-NATIVE" in cu:
                    return "red"
                return "lightblue"

            # Eventos de import_calendar (reservas + TPs)
            for e in import_events:
                cat = e.get("categories", "")
                all_events.append(
                    {
                        "uid": e.get("uid", ""),
                        "summary": e.get("summary", ""),
                        "description": e.get("description", ""),
                        "dtstart": str(e.get("dtstart", "")),
                        "dtend": str(e.get("dtend", "")),
                        "categories": cat,
                        "color": map_color(cat),
                        "editable": "PREP-TIME" not in str(cat).upper(),
                        "source": "import",
                    }
                )

            # Eventos de manual_calendar (sobrepõem ou acrescentam)
            for e in manual_events:
                uid = e.get("uid", "")
                cat = e.get("categories", "")
                existing = next((x for x in all_events if x["uid"] == uid), None)
                if existing:
                    existing.update(
                        {
                            "summary": e.get("summary", ""),
                            "description": e.get("description", ""),
                            "categories": cat,
                            "color": map_color(cat),
                            "editable": "PREP-TIME" not in str(cat).upper(),
                            "source": "manual",
                        }
                    )
                else:
                    all_events.append(
                        {
                            "uid": uid,
                            "summary": e.get("summary", ""),
                            "description": e.get("description", ""),
                            "dtstart": str(e.get("dtstart", "")),
                            "dtend": str(e.get("dtend", "")),
                            "categories": cat,
                            "color": map_color(cat),
                            "editable": "PREP-TIME" not in str(cat).upper(),
                            "source": "manual",
                        }
                    )

            logger.info("[MANUAL EDITOR] Total de %d eventos carregados", len(all_events))

            return (
                jsonify(
                    status="success",
                    events=all_events,
                    timestamp=datetime.now().isoformat(),
                ),
                200,
            )

        except Exception as e:
            logger.error("[MANUAL EDITOR] Erro ao carregar calendários: %s", e)
            return (
                jsonify(
                    status="error",
                    message=f"Erro ao carregar calendários: {str(e)}",
                ),
                500,
            )

    # ----------------------------------------------------------------------
    # GUARDAR CALENDÁRIO MANUAL + REGERAR MASTER
    # ----------------------------------------------------------------------
    @app.route("/api/manual/save", methods=["POST"])
    @api_login_required
    def api_manual_save():
        """
        Grava manual_calendar.ics e regenera master_calendar.ics.

        Payload JSON:
        {
            "ics_content": "BEGIN:VCALENDAR\\n...\\nEND:VCALENDAR",
            "notes": "Notas opcionais"
        }
        """
        try:
            from backend.sync import sync_local

            data = request.get_json() or {}
            ics_content = data.get("ics_content", "")
            notes = data.get("notes", "")

            if not ics_content or len(ics_content) < 20:
                return (
                    jsonify(
                        status="error",
                        message="Conteúdo ICS inválido (vazio ou muito curto)",
                    ),
                    400,
                )

            logger.info("[MANUAL EDITOR] Gravando manual_calendar.ics...")
            Path(cfg.MANUAL_CALENDAR_PATH).write_text(
                ics_content, encoding="utf-8"
            )

            # Opcional: logar notas
            if notes:
                logger.info("[MANUAL EDITOR] Notas: %s", notes)

            logger.info("[MANUAL EDITOR] Regenerando master_calendar.ics via sync_local()...")
            sync_result = sync_local()
            if sync_result.get("status") == "error":
                logger.error(
                    "[MANUAL EDITOR] Erro ao regenerar master: %s",
                    sync_result.get("message"),
                )
                return (
                    jsonify(
                        status="error",
                        message=f"Erro ao regenerar master_calendar: {sync_result.get('message')}",
                    ),
                    500,
                )

            # Git commit + push
            try:
                subprocess.run(
                    ["git", "add", "manual_calendar.ics", "master_calendar.ics"],
                    cwd=cfg.REPO_PATH,
                    check=True,
                    capture_output=True,
                )
                diff = subprocess.run(
                    ["git", "diff", "--cached", "--quiet"],
                    cwd=cfg.REPO_PATH,
                )
                if diff.returncode != 0:
                    commit_msg = (
                        f"🗓️ Manual calendar updated via editor by "
                        f"{session.get('username', 'unknown')}"
                    )
                    subprocess.run(
                        ["git", "commit", "-m", commit_msg],
                        cwd=cfg.REPO_PATH,
                        check=True,
                        capture_output=True,
                    )
                    subprocess.run(
                        ["git", "push", "origin", cfg.GITHUB_BRANCH],
                        cwd=cfg.REPO_PATH,
                        check=True,
                        capture_output=True,
                    )
                    logger.info("[MANUAL EDITOR] Git push concluído: %s", commit_msg)
            except subprocess.CalledProcessError as e:
                logger.warning("[MANUAL EDITOR] Git erro: %s", e)

            return (
                jsonify(
                    status="success",
                    message="Manual calendar guardado e master regenerado com sucesso!",
                    file_manual="manual_calendar.ics",
                    file_master="master_calendar.ics",
                    timestamp=datetime.now().isoformat(),
                ),
                200,
            )

        except Exception as e:
            logger.error("[MANUAL EDITOR] Erro no save: %s", e)
            return (
                jsonify(status="error", message=f"Erro ao guardar: {str(e)}"),
                500,
            )

    # ----------------------------------------------------------------------
    # DISPARAR WORKFLOW FULL AUTO (DASHBOARD)
    # ----------------------------------------------------------------------
    @app.route("/api/full-auto/sync-trigger", methods=["POST"])
    @api_login_required
    def api_full_auto_sync_trigger():
        """
        Dispara workflow GitHub: full_auto_workflow.yml
        (Sincroniza plataformas e regenera import/master)
        """
        try:
            if not cfg.GITHUB_TOKEN or not cfg.GITHUB_REPO:
                return (
                    jsonify(
                        status="error",
                        message="GitHub não configurado (token/repo em falta)",
                    ),
                    400,
                )

            headers = {
                "Authorization": f"Bearer {cfg.GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            payload = {
                "ref": cfg.GITHUB_BRANCH,
                "inputs": {
                    "triggered_by": session.get("username", "dashboard"),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
            }
            url = (
                f"https://api.github.com/repos/{cfg.GITHUB_REPO}/"
                "actions/workflows/full_auto_workflow.yml/dispatches"
            )

            logger.info("[FULL AUTO] Disparando workflow em %s...", cfg.GITHUB_REPO)
            resp = requests.post(url, headers=headers, json=payload, timeout=10)

            if resp.status_code == 204:
                logger.info("[FULL AUTO] Workflow disparado com sucesso")
                return (
                    jsonify(
                        status="success",
                        message=(
                            "✅ Sincronização de Master Calendar iniciada! "
                            "Aguarde 1-2 minutos."
                        ),
                        triggered_by=session.get("username", "dashboard"),
                        timestamp=datetime.utcnow().isoformat() + "Z",
                        workflow="full_auto_workflow.yml",
                    ),
                    200,
                )

            logger.error(
                "[FULL AUTO] GitHub retornou %s: %s", resp.status_code, resp.text
            )
            return (
                jsonify(
                    status="error",
                    message=f"Erro ao contactar GitHub: HTTP {resp.status_code}",
                ),
                resp.status_code,
            )

        except requests.exceptions.Timeout:
            logger.error("[FULL AUTO] Timeout ao contactar GitHub")
            return (
                jsonify(status="error", message="Timeout ao contactar GitHub"),
                504,
            )
        except requests.exceptions.ConnectionError:
            logger.error("[FULL AUTO] Erro de conexão com GitHub")
            return (
                jsonify(status="error", message="Erro de conexão com GitHub"),
                503,
            )
        except Exception as e:
            logger.error("[FULL AUTO] Erro inesperado: %s", e)
            return jsonify(status="error", message=str(e)), 500

    # ----------------------------------------------------------------------
    # STATUS (OPCIONAL)
    # ----------------------------------------------------------------------
    @app.route("/api/manual/status", methods=["GET"])
    @api_login_required
    def api_manual_status():
        """Status dos ficheiros de calendário."""
        try:
            from backend.ics import ICSHandler

            manual_exists = Path(cfg.MANUAL_CALENDAR_PATH).is_file()
            import_exists = Path(cfg.IMPORT_CALENDAR_PATH).is_file()
            master_exists = Path(cfg.MASTER_CALENDAR_PATH).is_file()

            manual_count = 0
            import_count = 0
            master_count = 0

            if manual_exists:
                try:
                    events = ICSHandler.read_ics_file(cfg.MANUAL_CALENDAR_PATH) or []
                    manual_count = len(events)
                except Exception:
                    pass

            if import_exists:
                try:
                    events = ICSHandler.read_ics_file(cfg.IMPORT_CALENDAR_PATH) or []
                    import_count = len(events)
                except Exception:
                    pass

            if master_exists:
                try:
                    events = ICSHandler.read_ics_file(cfg.MASTER_CALENDAR_PATH) or []
                    master_count = len(events)
                except Exception:
                    pass

            return (
                jsonify(
                    status="success",
                    manual={"exists": manual_exists, "count": manual_count},
                    import_cal={"exists": import_exists, "count": import_count},
                    master={"exists": master_exists, "count": master_count},
                    timestamp=datetime.now().isoformat(),
                ),
                200,
            )

        except Exception as e:
            logger.error("[MANUAL STATUS] Erro: %s", e)
            return jsonify(status="error", message=str(e)), 500
