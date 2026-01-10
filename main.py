"""
main.py - Flask (Render) como painel/API
- Painel web (login, dashboard)
- Sync local opcional via sync_engine.sync_local()
- Botão "Forçar Full Auto" que dispara workflow GitHub
- Leitura de .ics gerados (import/master/manual)
"""

from datetime import datetime
from pathlib import Path
import sys

from flask import (
    Flask,
    jsonify,
    request,
    render_template_string,
    redirect,
    url_for,
    session,
    send_file,
)
from flask_cors import CORS
import requests

from config import get_config
from auth import AuthManager, login_required, api_login_required
from ics_handler import ICSHandler
from sync_engine import sync_local  # sync local via scripts/sync_calendars

# Adicionar scripts/ ao path para email_handler
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from email_handler import EmailNotifier  # type: ignore

cfg = get_config()

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = cfg.SECRET_KEY
app.permanent_session_lifetime = cfg.PERMANENT_SESSION_LIFETIME
CORS(app, origins=[o.strip() for o in cfg.CORS_ORIGINS.split(",")])

# Verificação de configuração crítica
if not cfg.GITHUB_TOKEN:
    app.logger.warning(
        "⚠️  GITHUB_TOKEN não configurado - /api/full-auto/trigger pode não funcionar"
    )
if (
    not cfg.AIRBNB_ICAL_URL
    and not cfg.BOOKING_ICAL_URL
    and not cfg.VRBO_ICAL_URL
):
    app.logger.warning("⚠️  Nenhuma URL de calendário configurada")
if not cfg.EMAIL_USER or not cfg.EMAIL_PASSWORD:
    app.logger.warning(
        "⚠️  Email não configurado - notificações de email estão desativadas"
    )

app.logger.info(f"✅ Servidor iniciado em {cfg.FLASK_ENV} mode")
app.logger.info(f"✅ Repositório GitHub: {cfg.GITHUB_REPO}")
app.logger.info(f"✅ Source de .ics: {cfg.ICS_SOURCE}")

# Garante diretórios básicos
Path(cfg.REPO_PATH).mkdir(parents=True, exist_ok=True)
Path(cfg.DATA_DIR).mkdir(parents=True, exist_ok=True)
Path(cfg.LOG_FILE).touch(exist_ok=True)


# ---------------------------------------------------------------------
# HTML Views
# ---------------------------------------------------------------------


@app.route("/")
def index():
    if AuthManager.is_authenticated():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if AuthManager.is_authenticated():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if AuthManager.authenticate(username, password):
            AuthManager.login(username)
            return redirect(url_for("dashboard"))
        return (
            render_template_string(
                LOGIN_TEMPLATE, error="Utilizador ou password incorretos"
            ),
            401,
        )

    return render_template_string(LOGIN_TEMPLATE)


@app.route("/logout")
def logout():
    AuthManager.logout()
    return redirect(url_for("login_page"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template_string(DASHBOARD_TEMPLATE)


# ---------------------------------------------------------------------
# API - Health & Auth
# ---------------------------------------------------------------------


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify(
        {
            "status": "healthy",
            "version": "4.0",
            "environment": cfg.FLASK_ENV,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/auth/status", methods=["GET"])
def api_auth_status():
    return jsonify(
        {
            "authenticated": AuthManager.is_authenticated(),
            "username": session.get("username"),
            "timestamp": datetime.now().isoformat(),
        }
    )


# ---------------------------------------------------------------------
# API - Sync (local) opcional
# ---------------------------------------------------------------------


@app.route("/api/calendar/sync-local", methods=["POST"])
@api_login_required
def api_sync_local():
    result = sync_local()
    code = 200 if result.get("status") == "success" else 500

    # Enviar email se configurado
    if cfg.EMAIL_ON_ERROR:
        try:
            if result.get("status") != "success":
                EmailNotifier.send_error(
                    subject="Erro na sincronização local (Render)",
                    message=result.get("message", "Erro desconhecido"),
                    log_file=cfg.LOG_FILE if cfg.EMAIL_ATTACH_LOG else None,
                )
            else:
                # Notificação de sucesso opcional
                if cfg.NOTIFICATION_EMAIL:
                    EmailNotifier.send_success(
                        subject="Sincronização local completada (Render)",
                        message=(
                            "Sincronização completada com sucesso.\n"
                            f"Eventos importados: {result.get('import_count', 0)}\n"
                            f"Eventos master: {result.get('master_count', 0)}"
                        ),
                    )
        except Exception as e:
            app.logger.error(f"Erro ao enviar email de sync-local: {str(e)}")

    return jsonify(result), code


# ---------------------------------------------------------------------
# API - Forçar Full Auto (GitHub Actions)
# ---------------------------------------------------------------------


@app.route("/api/full-auto/trigger", methods=["POST"])
@api_login_required
def api_trigger_full_auto():
    """
    Dispara workflow GitHub `cfg.GITHUB_WORKFLOW` via API.
    Usa GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH.
    """
    if not cfg.GITHUB_TOKEN or not cfg.GITHUB_REPO or not cfg.GITHUB_WORKFLOW:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "GitHub não configurado (token/repo/workflow em falta).",
                }
            ),
            400,
        )

    triggered_by = session.get("username") or "render-dashboard"
    timestamp = datetime.utcnow().isoformat() + "Z"

    url = (
        f"https://api.github.com/repos/{cfg.GITHUB_REPO}/actions/workflows/"
        f"{cfg.GITHUB_WORKFLOW}/dispatches"
    )

    headers = {
        "Authorization": f"Bearer {cfg.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    payload = {
        "ref": cfg.GITHUB_BRANCH,
        "inputs": {"triggered_by": triggered_by, "timestamp": timestamp},
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 204:
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Workflow Full Auto disparado com sucesso.",
                        "triggered_by": triggered_by,
                        "timestamp": timestamp,
                    }
                ),
                200,
            )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Erro GitHub ({resp.status_code}): {resp.text}",
                }
            ),
            resp.status_code,
        )
    except requests.exceptions.Timeout:
        return jsonify({"status": "error", "message": "Timeout ao contactar GitHub."}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error", "message": "Erro de conexão com GitHub."}), 503
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------
# API - Calendars (.ics)
# ---------------------------------------------------------------------


@app.route("/api/calendar/import", methods=["GET"])
@api_login_required
def api_calendar_import():
    if not Path(cfg.IMPORT_CALENDAR_PATH).is_file():
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Import calendar not found",
                    "events": [],
                }
            ),
            404,
        )
    events = ICSHandler.read_ics_file(cfg.IMPORT_CALENDAR_PATH) or []
    return (
        jsonify(
            {
                "status": "success",
                "file": "import_calendar.ics",
                "events": events,
                "count": len(events),
                "timestamp": datetime.now().isoformat(),
            }
        ),
        200,
    )


@app.route("/api/calendar/master", methods=["GET"])
@api_login_required
def api_calendar_master():
    if not Path(cfg.MASTER_CALENDAR_PATH).is_file():
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Master calendar not found",
                    "events": [],
                }
            ),
            404,
        )
    events = ICSHandler.read_ics_file(cfg.MASTER_CALENDAR_PATH) or []
    return (
        jsonify(
            {
                "status": "success",
                "file": "master_calendar.ics",
                "events": events,
                "count": len(events),
                "timestamp": datetime.now().isoformat(),
            }
        ),
        200,
    )


@app.route("/api/calendar/manual", methods=["GET"])
@api_login_required
def api_calendar_manual():
    if not Path(cfg.MANUAL_CALENDAR_PATH).is_file():
        return (
            jsonify(
                {
                    "status": "success",
                    "file": "manual_calendar.ics",
                    "events": [],
                    "count": 0,
                    "message": "No manual events yet",
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            200,
        )
    events = ICSHandler.read_ics_file(cfg.MANUAL_CALENDAR_PATH) or []
    return (
        jsonify(
            {
                "status": "success",
                "file": "manual_calendar.ics",
                "events": events,
                "count": len(events),
                "timestamp": datetime.now().isoformat(),
            }
        ),
        200,
    )


@app.route("/api/calendar/status", methods=["GET"])
@api_login_required
def api_calendar_status():
    files = {
        "import_calendar": {
            "path": cfg.IMPORT_CALENDAR_PATH,
            "exists": Path(cfg.IMPORT_CALENDAR_PATH).is_file(),
        },
        "master_calendar": {
            "path": cfg.MASTER_CALENDAR_PATH,
            "exists": Path(cfg.MASTER_CALENDAR_PATH).is_file(),
        },
        "manual_calendar": {
            "path": cfg.MANUAL_CALENDAR_PATH,
            "exists": Path(cfg.MANUAL_CALENDAR_PATH).is_file(),
        },
    }

    for info in files.values():
        if info["exists"]:
            try:
                size = Path(info["path"]).stat().st_size
                info["size_bytes"] = size
                info["size_kb"] = round(size / 1024, 2)
            except Exception:
                pass

    return (
        jsonify(
            {
                "status": "success",
                "repo_path": cfg.REPO_PATH,
                "files": files,
                "timestamp": datetime.now().isoformat(),
            }
        ),
        200,
    )


@app.route("/api/calendar/export", methods=["GET"])
@api_login_required
def api_calendar_export():
    cal_type = request.args.get("type", "manual")
    if cal_type == "manual":
        path = cfg.MANUAL_CALENDAR_PATH
    elif cal_type == "master":
        path = cfg.MASTER_CALENDAR_PATH
    elif cal_type == "import":
        path = cfg.IMPORT_CALENDAR_PATH
    else:
        return jsonify({"status": "error", "message": "Invalid calendar type"}), 400

    if not Path(path).is_file():
        return (
            jsonify({"status": "error", "message": f"{cal_type} calendar not found"}),
            404,
        )

    return send_file(path, as_attachment=True, download_name=f"{cal_type}_calendar.ics")


# ---------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------


@app.errorhandler(404)
def handle_404(_):
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404


@app.errorhandler(500)
def handle_500(_):
    return jsonify({"status": "error", "message": "Internal server error"}), 500


# ---------------------------------------------------------------------
# Templates mínimos (login + dashboard simples)
# ---------------------------------------------------------------------

LOGIN_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-PT">
<head>
  <meta charset="UTF-8">
  <title>Login - Rental Calendar Sync</title>
</head>
<body>
  <h1>Login</h1>
  {% if error %}<p style="color:red">{{ error }}</p>{% endif %}
  <form method="POST">
    <label>Utilizador: <input type="text" name="username" required></label><br>
    <label>Password: <input type="password" name="password" required></label><br>
    <button type="submit">Entrar</button>
  </form>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-PT">
<head>
  <meta charset="UTF-8">
  <title>Dashboard - Rental Calendar Sync</title>
</head>
<body>
  <h1>Dashboard</h1>
  <p>Bem-vindo, {{ session.username }}!</p>
  <a href="/logout">Logout</a>
  <hr>
  <button onclick="syncLocal()">Sync Local (Render)</button>
  <button onclick="triggerFullAuto()">Forçar Full Auto (GitHub)</button>
  <div id="status"></div>
  <script>
    async function syncLocal() {
      const el = document.getElementById('status');
      el.textContent = 'A sincronizar localmente...';
      try {
        const res = await fetch('/api/calendar/sync-local', {method: 'POST'});
        const data = await res.json();
        el.textContent = JSON.stringify(data);
      } catch (e) {
        el.textContent = 'Erro: ' + e.message;
      }
    }
    async function triggerFullAuto() {
      const el = document.getElementById('status');
      el.textContent = 'A disparar workflow GitHub...';
      try {
        const res = await fetch('/api/full-auto/trigger', {method: 'POST'});
        const data = await res.json();
        el.textContent = JSON.stringify(data);
      } catch (e) {
        el.textContent = 'Erro: ' + e.message;
      }
    }
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=cfg.PORT, debug=cfg.DEBUG)
