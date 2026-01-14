#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - Aplicação Flask Principal (v4.0)
Sincronização de calendários com autenticação por sessões
Versão: 4.0
Data: 14 de Janeiro de 2026
Desenvolvido por: PBrandão
"""
from datetime import datetime, timedelta
from pathlib import Path
import os
import json
from flask import (
    Flask, jsonify, request, render_template_string, redirect, url_for, session,
)

# ============================================================================
# IMPORTS - AUTH
# ============================================================================
from auth import AuthManager, login_required, api_login_required
from backend.sync import ManualCalendarManager, sync_local

# ============================================================================
# FLASK APP SETUP
# ============================================================================
app = Flask(__name__, static_folder="static", static_url_path="/static")

# Configuração de sessão (CRÍTICO)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.permanent_session_lifetime = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = False  # True em produção com HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

app.logger.info(f"✅ Servidor Flask iniciado - v4.0")

# ============================================================================
# HTML VIEWS
# ============================================================================
@app.route("/")
def index():
    """Redireciona para dashboard ou login"""
    if AuthManager.is_authenticated():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))


@app.route("/login", methods=["GET", "POST"])
def login_page():
    """Página de login"""
    if AuthManager.is_authenticated():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return render_template_string(LOGIN_TEMPLATE, error="Preencha todos os campos"), 400
        if AuthManager.authenticate(username, password):
            AuthManager.login(username)
            app.logger.info(f"✅ Login bem-sucedido: {username}")
            return redirect(url_for("dashboard"))
        app.logger.warning(f"❌ Tentativa de login falhada: {username}")
        return render_template_string(LOGIN_TEMPLATE, error="Utilizador ou password incorretos"), 401
    return render_template_string(LOGIN_TEMPLATE)


@app.route("/logout")
def logout():
    """Logout"""
    user = AuthManager.get_current_user()
    AuthManager.logout()
    app.logger.info(f"✅ Logout: {user}")
    return redirect(url_for("login_page"))


@app.route("/dashboard")
@login_required
def dashboard():
    """Dashboard principal"""
    app.logger.info(f"✅ Acesso ao dashboard: {AuthManager.get_current_user()}")
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        app.logger.error("❌ static/index.html não encontrado")
        return jsonify({"error": "Dashboard HTML not found"}), 404
    except Exception as e:
        app.logger.error(f"❌ Erro ao ler dashboard: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/manual-editor")
@login_required
def manual_editor_page():
    """Editor manual de calendários"""
    app.logger.info(f"✅ Acesso ao editor manual: {AuthManager.get_current_user()}")
    try:
        with open("static/manual_calendar.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        app.logger.error("❌ static/manual_calendar.html não encontrado")
        return jsonify({"error": "Manual Editor HTML not found"}), 404
    except Exception as e:
        app.logger.error(f"❌ Erro ao ler manual editor: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# API - AUTENTICAÇÃO
# ============================================================================
@app.route("/api/auth/check", methods=["GET"])
def api_auth_check():
    """GET: Verifica autenticação (SEM decorator - precisa funcionar no login)"""
    if AuthManager.is_authenticated():
        return jsonify({
            "status": "success",
            "authenticated": True,
            "user": AuthManager.get_current_user()
        }), 200
    return jsonify({
        "status": "error",
        "authenticated": False,
        "message": "Not authenticated"
    }), 401


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    """POST: Login via JSON"""
    try:
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")
        if not username or not password:
            return jsonify({
                "status": "error",
                "message": "Missing credentials"
            }), 400
        if AuthManager.authenticate(username, password):
            AuthManager.login(username)
            app.logger.info(f"✅ API Login: {username}")
            return jsonify({
                "status": "success",
                "message": "Login successful",
                "user": username
            }), 200
        app.logger.warning(f"❌ API Login falhou: {username}")
        return jsonify({
            "status": "error",
            "message": "Invalid credentials"
        }), 401
    except Exception as e:
        app.logger.error(f"❌ Erro ao fazer login: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/auth/logout", methods=["POST"])
@api_login_required
def api_auth_logout():
    """POST: Logout"""
    try:
        user = AuthManager.get_current_user()
        AuthManager.logout()
        app.logger.info(f"✅ API Logout: {user}")
        return jsonify({
            "status": "success",
            "message": "Logout successful"
        }), 200
    except Exception as e:
        app.logger.error(f"❌ Erro ao fazer logout: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================
# API - CALENDÁRIOS - CARREGAMENTO
# ============================================================================
@app.route("/api/calendar/import", methods=["GET"])
@api_login_required
def api_calendar_import():
    """GET: Retorna eventos do import_calendar.ics"""
    try:
        manager = ManualCalendarManager()
        events = manager.load_import_events()
        
        return jsonify({
            "status": "success",
            "file": "import_calendar.ics",
            "count": len(events),
            "events": events,
            "timestamp": datetime.now().isoformat(),
        }), 200
    except Exception as e:
        app.logger.error(f"❌ Erro ao ler import_calendar.ics: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/calendar/manual", methods=["GET"])
@api_login_required
def api_calendar_manual():
    """GET: Retorna eventos do manual_calendar.ics (local)"""
    try:
        manager = ManualCalendarManager()
        events = manager.load_manual_events()
        
        return jsonify({
            "status": "success",
            "file": "manual_calendar.ics",
            "count": len(events),
            "events": events,
            "timestamp": datetime.now().isoformat(),
        }), 200
    except Exception as e:
        app.logger.error(f"❌ Erro ao ler manual_calendar.ics: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================
# API - CALENDÁRIOS - OPERAÇÕES MANUAIS v4.0
# ============================================================================
@app.route("/api/calendar/block", methods=["POST"])
@api_login_required
def api_calendar_block():
    """POST: Bloquear datas (MANUAL-BLOCK)"""
    try:
        data = request.get_json() or {}
        dates = data.get("dates", [])  # Lista de datas em formato YYYY-MM-DD
        
        if not dates or not isinstance(dates, list):
            return jsonify({"status": "error", "message": "Invalid dates format"}), 400
        
        manager = ManualCalendarManager()
        result = manager.block_dates(dates)
        
        app.logger.info(f"✅ Bloqueadas {len(dates)} data(s)")
        return jsonify({
            "status": "success",
            "message": f"{len(dates)} data(s) bloqueada(s)!",
            "count": len(dates),
            "blocked_dates": dates
        }), 200
    
    except Exception as e:
        app.logger.error(f"❌ Erro ao bloquear datas: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/calendar/remove", methods=["POST"])
@api_login_required
def api_calendar_remove():
    """POST: Remover evento (MANUAL-REMOVE)"""
    try:
        data = request.get_json() or {}
        dates = data.get("dates", [])  # Lista de datas em formato YYYY-MM-DD
        
        if not dates or not isinstance(dates, list):
            return jsonify({"status": "error", "message": "Invalid dates format"}), 400
        
        manager = ManualCalendarManager()
        result = manager.remove_events(dates)
        
        app.logger.info(f"✅ Removidas {len(dates)} data(s)")
        return jsonify({
            "status": "success",
            "message": f"{len(dates)} data(s) desbloqueada(s)!",
            "count": len(dates),
            "removed_dates": dates
        }), 200
    
    except Exception as e:
        app.logger.error(f"❌ Erro ao remover eventos: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/calendar/clear", methods=["POST"])
@api_login_required
def api_calendar_clear():
    """POST: Limpar datas e eventos do manual_calendar.ics"""
    try:
        data = request.get_json() or {}
        dates = data.get("dates", [])  # Lista de datas em formato YYYY-MM-DD
        
        if not dates or not isinstance(dates, list):
            return jsonify({"status": "error", "message": "Invalid dates format"}), 400
        
        manager = ManualCalendarManager()
        result = manager.clear_events(dates)
        
        app.logger.info(f"✅ Limpas {len(dates)} data(s) do manual_calendar.ics")
        return jsonify({
            "status": "success",
            "message": f"{len(dates)} evento(s) removido(s) do manual_calendar.ics!",
            "count": len(dates),
            "cleared_dates": dates
        }), 200
    
    except Exception as e:
        app.logger.error(f"❌ Erro ao limpar eventos: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/calendar/save", methods=["POST"])
@api_login_required
def api_calendar_save():
    """POST: Guardar alterações e gerar ficheiros ICS"""
    try:
        manager = ManualCalendarManager()
        
        # Gerar manual_calendar.ics
        manager.save_manual_calendar()
        
        # Sincronizar e gerar master_calendar.ics
        sync_result = sync_local()
        
        if sync_result.get("status") != "success":
            return jsonify({
                "status": "error",
                "message": sync_result.get("message", "Erro ao sincronizar")
            }), 500
        
        app.logger.info(f"✅ Alterações guardadas com sucesso!")
        return jsonify({
            "status": "success",
            "message": "✅ Alterações guardadas com sucesso!",
            "sync_result": sync_result
        }), 200
    
    except Exception as e:
        app.logger.error(f"❌ Erro ao guardar alterações: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================
# API - SINCRONIZAÇÃO
# ============================================================================
@app.route("/api/sync/local", methods=["POST"])
@api_login_required
def api_sync_local():
    """POST: Executa sincronização local"""
    try:
        user = AuthManager.get_current_user()
        app.logger.info(f"🔄 Sincronização local iniciada por {user}")
        
        result = sync_local()
        
        if result.get("status") != "success":
            return jsonify(result), 500
        
        return jsonify(result), 200
    
    except Exception as e:
        app.logger.error(f"❌ Erro ao sincronizar localmente: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/sync/github", methods=["POST"])
@api_login_required
def api_sync_github():
    """POST: Dispara workflow GitHub (placeholder)"""
    try:
        user = AuthManager.get_current_user()
        app.logger.info(f"✅ Sincronização GitHub iniciada por {user}")
        
        return jsonify({
            "status": "success",
            "message": "✅ Sincronização GitHub concluída! Aguarde o deploy…",
            "note": "Modo teste - GitHub Actions não é acionada. Implementar trigger real em produção.",
            "timestamp": datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        app.logger.error(f"❌ Erro ao sincronizar GitHub: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/status/files", methods=["GET"])
@api_login_required
def api_status_files():
    """GET: Status dos ficheiros ICS"""
    try:
        files = [
            {
                "name": "import_calendar.ics",
                "exists": Path("import_calendar.ics").exists(),
                "size": "N/A"
            },
            {
                "name": "master_calendar.ics",
                "exists": Path("master_calendar.ics").exists(),
                "size": "N/A"
            },
            {
                "name": "manual_calendar.ics",
                "exists": Path("manual_calendar.ics").exists(),
                "size": "N/A"
            },
        ]
        return jsonify({
            "status": "success",
            "files": files,
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        app.logger.error(f"❌ Erro ao obter status dos ficheiros: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================
# TEMPLATES HTML
# ============================================================================
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-PT">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rental Calendar Sync - Login</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
            width: 100%;
            max-width: 400px;
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 1.5rem;
            font-size: 1.5rem;
        }
        .form-group {
            margin-bottom: 1rem;
        }
        label {
            display: block;
            margin-bottom: 0.5rem;
            color: #555;
            font-weight: 500;
        }
        input {
            width: 100%;
            padding: 0.75rem;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 1rem;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        button {
            width: 100%;
            padding: 0.75rem;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 1rem;
            cursor: pointer;
            transition: background 0.3s;
        }
        button:hover {
            background: #5568d3;
        }
        .error {
            color: #e74c3c;
            background: #fadbd8;
            padding: 0.75rem;
            border-radius: 4px;
            margin-bottom: 1rem;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>🗓️ Rental Calendar Sync</h1>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        <form method="POST">
            <div class="form-group">
                <label for="username">Utilizador</label>
                <input type="text" id="username" name="username" required autofocus>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Entrar</button>
        </form>
    </div>
</body>
</html>
"""

# ============================================================================
# ERROR HANDLERS
# ============================================================================
@app.errorhandler(404)
def not_found(error):
    return jsonify({"status": "error", "message": "Not Found"}), 404


@app.errorhandler(500)
def server_error(error):
    app.logger.error(f"❌ Server Error: {error}")
    return jsonify({"status": "error", "message": "Internal Server Error"}), 500


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
