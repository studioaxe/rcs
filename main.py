"""
main.py - Flask (Render Free) como painel/API
- Lê .ics do GitHub repo (persistente GRÁTIS)
- Trigger Full Auto (disparar workflow GitHub)
- Interface web (login, dashboard)
"""

from datetime import datetime
from pathlib import Path
import sys
import requests

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

from config import get_config
from auth import AuthManager, login_required, api_login_required
from ics_handler import ICSHandler
from sync_engine import sync_local

# Email handler
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from email_handler import EmailNotifier  # type: ignore

cfg = get_config()

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = cfg.SECRET_KEY
app.permanent_session_lifetime = cfg.PERMANENT_SESSION_LIFETIME
CORS(app, origins=[o.strip() for o in cfg.CORS_ORIGINS.split(",")])

# Verificação de configuração crítica
if not cfg.GITHUB_TOKEN:
    app.logger.warning("⚠️ GITHUB_TOKEN não configurado - /api/full-auto/trigger pode não funcionar")
if not cfg.AIRBNB_ICAL_URL and not cfg.BOOKING_ICAL_URL and not cfg.VRBO_ICAL_URL:
    app.logger.warning("⚠️ Nenhuma URL de calendário configurada")
if not cfg.EMAIL_USER or not cfg.EMAIL_PASSWORD:
    app.logger.warning("⚠️ Email não configurado - notificações desabilitadas")

app.logger.info(f"✅ Servidor iniciado em {cfg.FLASK_ENV} mode")
app.logger.info(f"✅ Repositório GitHub: {cfg.GITHUB_REPO}")
app.logger.info(f"✅ Source de .ics: GitHub (raw.githubusercontent.com)")

# Garante diretórios
Path(cfg.REPO_PATH).mkdir(parents=True, exist_ok=True)
Path(cfg.DATA_DIR).mkdir(parents=True, exist_ok=True)


# Helper: Ler ICS do GitHub
def read_ics_from_github(url: str) -> list:
    """Lê ficheiro ICS diretamente do GitHub via raw.githubusercontent.com"""
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return ICSHandler.parse_ics_content(resp.text) or []
        return []
    except Exception as e:
        app.logger.error(f"Erro ao ler ICS de GitHub ({url}): {str(e)}")
        return []


# =====================================================================
# HTML Views
# =====================================================================


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
            render_template_string(LOGIN_TEMPLATE, error="Utilizador ou password incorretos"),
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


# =====================================================================
# API - Health & Auth
# =====================================================================


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify(
        {
            "status": "healthy",
            "version": "4.0",
            "environment": cfg.FLASK_ENV,
            "ics_source": "github",
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


# =====================================================================
# API - Sync Local (GitHub Actions via workflow trigger)
# =====================================================================


@app.route("/api/calendar/sync-local", methods=["POST"])
@api_login_required
def api_sync_local():
    """Dispara workflow GitHub para sync"""
    return api_trigger_full_auto()  # Alias para /api/full-auto/trigger


# =====================================================================
# API - Full Auto Trigger (GitHub Actions)
# =====================================================================


@app.route("/api/full-auto/trigger", methods=["POST"])
@api_login_required
def api_trigger_full_auto():
    """Dispara workflow GitHub full_auto_workflow.yml"""
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
                        "message": "Workflow disparado com sucesso. Aguarde 1-2 min.",
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


# =====================================================================
# API - Calendars (leitura do GitHub)
# =====================================================================


@app.route("/api/calendar/import", methods=["GET"])
@api_login_required
def api_calendar_import():
    """Lê import_calendar.ics do GitHub"""
    events = read_ics_from_github(cfg.IMPORT_CALENDAR_URL)
    if not events:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Import calendar not found no GitHub",
                    "events": [],
                }
            ),
            404,
        )
    return (
        jsonify(
            {
                "status": "success",
                "file": "import_calendar.ics",
                "source": "github",
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
    """Lê master_calendar.ics do GitHub"""
    events = read_ics_from_github(cfg.MASTER_CALENDAR_URL)
    if not events:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Master calendar not found no GitHub",
                    "events": [],
                }
            ),
            404,
        )
    return (
        jsonify(
            {
                "status": "success",
                "file": "master_calendar.ics",
                "source": "github",
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
    """Lê manual_calendar.ics (local ou GitHub)"""
    # Tenta local primeiro
    if Path(cfg.MANUAL_CALENDAR_PATH).is_file():
        events = ICSHandler.read_ics_file(cfg.MANUAL_CALENDAR_PATH) or []
        return (
            jsonify(
                {
                    "status": "success",
                    "file": "manual_calendar.ics",
                    "source": "local",
                    "events": events,
                    "count": len(events),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            200,
        )

    # Se não existe, retorna vazio
    return (
        jsonify(
            {
                "status": "success",
                "file": "manual_calendar.ics",
                "source": "none",
                "events": [],
                "count": 0,
                "message": "No manual events yet",
                "timestamp": datetime.now().isoformat(),
            }
        ),
        200,
    )


@app.route("/api/calendar/status", methods=["GET"])
@api_login_required
def api_calendar_status():
    """Status dos calendários (GitHub + local)"""
    return (
        jsonify(
            {
                "status": "success",
                "ics_source": "GitHub (raw.githubusercontent.com)",
                "import_calendar_url": cfg.IMPORT_CALENDAR_URL,
                "master_calendar_url": cfg.MASTER_CALENDAR_URL,
                "manual_calendar_local": cfg.MANUAL_CALENDAR_PATH,
                "github_repo": cfg.GITHUB_REPO,
                "timestamp": datetime.now().isoformat(),
            }
        ),
        200,
    )


@app.route("/api/calendar/export", methods=["GET"])
@api_login_required
def api_calendar_export():
    """Export manual calendar (local file)"""
    cal_type = request.args.get("type", "manual")

    if cal_type != "manual":
        return (
            jsonify({"status": "error", "message": "Only manual calendar can be exported"}),
            400,
        )

    if not Path(cfg.MANUAL_CALENDAR_PATH).is_file():
        return (
            jsonify({"status": "error", "message": "Manual calendar not found"}),
            404,
        )

    return send_file(
        cfg.MANUAL_CALENDAR_PATH,
        as_attachment=True,
        download_name="manual_calendar.ics",
    )


# =====================================================================
# Error Handlers
# =====================================================================


@app.errorhandler(404)
def handle_404(_):
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404


@app.errorhandler(500)
def handle_500(_):
    return jsonify({"status": "error", "message": "Internal server error"}), 500


# =====================================================================
# Templates
# =====================================================================

LOGIN_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-PT">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Login - Rental Calendar Sync</title>
  <style>
    body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f5f5f5; }
    .login-box { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); width: 300px; }
    h1 { text-align: center; color: #333; margin-top: 0; }
    .error { color: #d32f2f; padding: 10px; background: #ffebee; border-radius: 4px; margin-bottom: 20px; }
    label { display: block; margin-top: 15px; font-weight: bold; color: #555; }
    input { width: 100%; padding: 8px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
    button { width: 100%; padding: 10px; margin-top: 20px; background: #1976d2; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
    button:hover { background: #1565c0; }
  </style>
</head>
<body>
  <div class="login-box">
    <h1>Login</h1>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="POST">
      <label>Utilizador:</label>
      <input type="text" name="username" required autofocus>
      <label>Password:</label>
      <input type="password" name="password" required>
      <button type="submit">Entrar</button>
    </form>
  </div>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-PT">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dashboard - Rental Calendar Sync</title>
  <style>
    body { font-family: sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
    .container { max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    h1 { color: #333; margin-top: 0; }
    .header { display: flex; justify-content: space-between; align-items: center; }
    .logout { padding: 10px 20px; background: #d32f2f; color: white; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; }
    .logout:hover { background: #b71c1c; }
    .button-group { margin: 20px 0; display: flex; gap: 10px; flex-wrap: wrap; }
    button { padding: 10px 20px; background: #1976d2; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
    button:hover { background: #1565c0; }
    button:disabled { background: #ccc; cursor: not-allowed; }
    .status { margin-top: 20px; padding: 15px; border-radius: 4px; }
    .success { background: #e8f5e9; color: #2e7d32; border-left: 4px solid #4caf50; }
    .error { background: #ffebee; color: #c62828; border-left: 4px solid #f44336; }
    .info { background: #e3f2fd; color: #1565c0; border-left: 4px solid #2196f3; }
    pre { background: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h1>🗓️ Rental Calendar Sync v4.0</h1>
        <p>Bem-vindo, <strong>{{ session.username }}</strong>!</p>
      </div>
      <a href="/logout" class="logout">Logout</a>
    </div>

    <div class="button-group">
      <button onclick="triggerFullAuto()" id="fullAutoBtn">🚀 Sync Full Auto (GitHub)</button>
      <button onclick="getStatus()">📊 Ver Status</button>
    </div>

    <div id="status"></div>

    <hr>
    <h3>ℹ️ Informações</h3>
    <pre id="info"></pre>
  </div>

  <script>
    async function triggerFullAuto() {
      const btn = document.getElementById('fullAutoBtn');
      const status = document.getElementById('status');
      
      btn.disabled = true;
      status.innerHTML = '<div class="info">⏳ A disparar workflow GitHub... aguarde 1-2 min</div>';
      
      try {
        const res = await fetch('/api/full-auto/trigger', { method: 'POST' });
        const data = await res.json();
        
        if (data.status === 'success') {
          status.innerHTML = `<div class="success">✅ ${data.message}<br>Disparado por: ${data.triggered_by}</div>`;
        } else {
          status.innerHTML = `<div class="error">❌ ${data.message}</div>`;
        }
      } catch (e) {
        status.innerHTML = `<div class="error">❌ Erro: ${e.message}</div>`;
      } finally {
        btn.disabled = false;
      }
    }

    async function getStatus() {
      try {
        const res = await fetch('/api/calendar/status');
        const data = await res.json();
        const info = document.getElementById('info');
        info.textContent = JSON.stringify(data, null, 2);
      } catch (e) {
        alert('Erro: ' + e.message);
      }
    }

    // Load info on page load
    window.onload = getStatus;
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=cfg.PORT, debug=cfg.DEBUG)
