#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
main.py - VERSÃO CORRIGIDA V1.3
Versão: 1.3 - Git commit + push IMPLEMENTADO
Data: 20 de Janeiro de 2026

MUDANÇA CRÍTICA:
✅ GET /api/calendar/import:
   1. Executa sync_calendars()
   2. Git add + commit + push em import_calendar.ics
   3. Git add + commit + push em master_calendar.ics
   
✅ Isto garante que os ficheiros .ics SEMPRE são guardados no repositório
"""

import os
import sys
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Flask imports
from flask import Flask, render_template, request, redirect, url_for, jsonify, session

# Backend imports
sys.path.insert(0, str(Path(__file__).parent))

from auth import AuthManager, login_required, api_login_required
from sync import sync_calendars
from backend.notifier import EmailNotifier
from backend.ics import ICSHandler
from backend.manual_editor import ManualEditorHandler

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# Paths
REPO_PATH = Path(__file__).parent
STATIC_PATH = REPO_PATH / "static"
TEMPLATES_PATH = REPO_PATH / "templates"

# Criar diretórios se não existirem
STATIC_PATH.mkdir(exist_ok=True)
TEMPLATES_PATH.mkdir(exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(REPO_PATH / 'app.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)

# ============================================================================
# FLASK APP
# ============================================================================

app = Flask(__name__, static_folder=str(STATIC_PATH), template_folder=str(TEMPLATES_PATH))
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-prod')
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_SESSION_SECURE', 'False').lower() == 'true'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 7  # 7 days

notifier = EmailNotifier()

# ============================================================================
# ROTAS HTML
# ============================================================================

@app.route('/', methods=['GET'])
def index():
    """Redireciona para dashboard se autenticado, senão para login."""
    if AuthManager.is_authenticated():
        return redirect(url_for('dashboard_page'))
    return redirect(url_for('login_page'))


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Página de login."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            return render_template('login.html', error='Username e password obrigatórios'), 400
        
        if AuthManager.authenticate(username, password):
            AuthManager.login(username)
            logger.info(f"✅ Login bem-sucedido: {username}")
            return redirect(url_for('dashboard_page'))
        else:
            logger.warning(f"❌ Tentativa de login falhou: {username}")
            return render_template('login.html', error='Credenciais inválidas'), 401
    
    return render_template('login.html')


@app.route('/logout', methods=['GET', 'POST'])
def logout_page():
    """Logout e redireciona para login."""
    user = AuthManager.get_current_user()
    AuthManager.logout()
    logger.info(f"✅ Logout: {user}")
    return redirect(url_for('login_page'))


@app.route('/dashboard', methods=['GET'])
@login_required
def dashboard_page():
    """Dashboard com botões de sincronização e editor manual."""
    user = AuthManager.get_current_user()
    return render_template('dashboard.html', user=user)


@app.route('/manual-editor', methods=['GET'])
@login_required
def manual_editor_page():
    """Página do editor manual de calendário."""
    user = AuthManager.get_current_user()
    return render_template('manual_editor.html', user=user)

# ============================================================================
# UTILITÁRIOS GIT
# ============================================================================

def git_commit_push(files: List[str], message: str) -> bool:
    """
    Faz git add + commit + push para ficheiros específicos.
    
    Args:
        files: Lista de ficheiros (ex: ['import_calendar.ics', 'master_calendar.ics'])
        message: Mensagem do commit
    
    Returns:
        True se sucesso, False se falha
    """
    try:
        logger.info(f"[GIT] 🔄 Git add + commit + push para {len(files)} ficheiro(s)")
        
        # Git add dos ficheiros específicos
        for file in files:
            logger.info(f"[GIT] ➕ git add {file}")
            subprocess.run(
                ['git', 'add', file],
                cwd=str(REPO_PATH),
                check=True,
                capture_output=True,
                timeout=30
            )
        
        # Git commit
        logger.info(f"[GIT] 📝 git commit -m '{message}'")
        try:
            result = subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=str(REPO_PATH),
                check=True,
                capture_output=True,
                timeout=30
            )
            logger.info(f"[GIT] ✅ Commit concluído")
        except subprocess.CalledProcessError as e:
            # Pode falhar se não houver mudanças (working tree clean)
            if "nothing to commit" in e.stderr.decode():
                logger.info(f"[GIT] ℹ️ Sem mudanças para commit (working tree clean)")
                return True
            else:
                logger.error(f"[GIT] ❌ Commit falhou: {e.stderr.decode()}")
                return False
        
        # Git push
        logger.info(f"[GIT] 🚀 git push")
        subprocess.run(
            ['git', 'push'],
            cwd=str(REPO_PATH),
            check=True,
            capture_output=True,
            timeout=60
        )
        logger.info(f"[GIT] ✅ Push concluído")
        
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("[GIT] ❌ Timeout na operação git")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"[GIT] ❌ Git error: {e.stderr.decode() if e.stderr else str(e)}")
        return False
    except Exception as e:
        logger.error(f"[GIT] ❌ Erro inesperado: {e}", exc_info=True)
        return False

# ============================================================================
# API ENDPOINTS - SESSÃO
# ============================================================================

@app.route('/api/session', methods=['GET'])
def api_session():
    """Retorna informação de sessão atual."""
    session_info = AuthManager.get_session_info()
    return jsonify({
        'status': 'success',
        'session': session_info
    })

# ============================================================================
# API ENDPOINTS - SINCRONIZAÇÃO
# ============================================================================

@app.route('/api/sync', methods=['POST'])
@api_login_required
def api_sync():
    """
    Força sincronização imediata.
    """
    try:
        logger.info("=" * 80)
        logger.info("🔄 [API] Sincronização iniciada (Manual)...")
        logger.info("=" * 80)
        
        success = sync_calendars()
        
        if success:
            logger.info("=" * 80)
            logger.info("✅ [API] Sincronização concluída com sucesso")
            logger.info("=" * 80)
            
            # Git commit + push
            git_commit_push(
                ['import_calendar.ics', 'master_calendar.ics'],
                'sync API manual - Sincronização de calendários [AUTO]'
            )
            
            notifier.send_success(total_events=0, reserved_count=0)
            return jsonify({
                'status': 'success',
                'message': 'Sincronização completada com sucesso',
                'timestamp': datetime.now().isoformat()
            }), 200
        else:
            logger.error("=" * 80)
            logger.error("❌ [API] Sincronização falhou")
            logger.error("=" * 80)
            return jsonify({
                'status': 'error',
                'message': 'Erro na sincronização',
                'timestamp': datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ [API] Erro na sincronização: {e}")
        logger.error("=" * 80)
        notifier.send_error(f"API sync error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ============================================================================
# API ENDPOINTS - CALENDÁRIO (CRÍTICO: SYNC + GIT)
# ============================================================================

@app.route('/api/calendar/import', methods=['GET'])
@api_login_required
def api_calendar_import():
    """
    GET /api/calendar/import
    
    🔴 FLUXO CRÍTICO COMPLETO:
    1. Executa sync_calendars()
       ↓ Importa reservas nativas
       ↓ Aplica TPs
       ↓ Atualiza import_calendar.ics
       ↓ Atualiza master_calendar.ics
    2. Git add + commit + push (import_calendar.ics + master_calendar.ics)
    3. Carrega import_calendar.ics atualizado
    
    Response: Lista de dicts com eventos sincronizados
    """
    try:
        logger.info("=" * 80)
        logger.info("[API] 📥 GET /api/calendar/import")
        logger.info("[API] 🔄 EXECUTANDO SYNC.PY + GIT (CRÍTICO)...")
        logger.info("=" * 80)
        
        # ================================================================
        # PASSO 1: SINCRONIZAR (IMPORTAR RESERVAS + APLICAR TPs)
        # ================================================================
        logger.info("[API] 🚀 Iniciando sync_calendars()...")
        sync_start = datetime.now()
        
        try:
            sync_success = sync_calendars()
            sync_end = datetime.now()
            sync_duration = (sync_end - sync_start).total_seconds()
            
            if sync_success:
                logger.info(f"[API] ✅ Sync.py concluído com SUCESSO ({sync_duration:.2f}s)")
            else:
                logger.warning(f"[API] ⚠️ Sync.py retornou False ({sync_duration:.2f}s)")
        except Exception as sync_error:
            logger.error(f"[API] ❌ Erro durante sync.py: {sync_error}", exc_info=True)
            logger.warning("[API] ⚠️ Continuando mesmo com erro...")
        
        # ================================================================
        # PASSO 2: GIT COMMIT + PUSH (CRÍTICO)
        # ================================================================
        logger.info("[API] 📤 Git commit + push (import_calendar.ics, master_calendar.ics)")
        git_success = git_commit_push(
            ['import_calendar.ics', 'master_calendar.ics'],
            'import_calendar.ics + master_calendar.ics - Sincronização automática [AUTO]'
        )
        
        if git_success:
            logger.info("[API] ✅ Git commit + push concluído")
        else:
            logger.warning("[API] ⚠️ Git commit + push falhou (continuando)")
        
        # ================================================================
        # PASSO 3: CARREGAR IMPORT_CALENDAR.ICS ATUALIZADO
        # ================================================================
        logger.info("[API] 📖 Carregando import_calendar.ics ATUALIZADO...")
        editor = ManualEditorHandler()
        events = editor.load_import_events()
        
        logger.info(f"[API] ✅ Carregados {len(events)} eventos do import_calendar.ics")
        logger.info("=" * 80)
        
        return jsonify(events), 200
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"[API] ❌ ERRO ao carregar import: {e}", exc_info=True)
        logger.error("=" * 80)
        return jsonify([]), 500


@app.route('/api/calendar/manual', methods=['GET'])
@api_login_required
def api_calendar_manual():
    """
    GET /api/calendar/manual
    
    Carrega eventos do manual_calendar.ics
    (Após sync ter atualizado o import)
    
    Response: Lista de dicts com eventos manuais
    """
    try:
        logger.info("[API] 📥 GET /api/calendar/manual")
        editor = ManualEditorHandler()
        events = editor.load_manual_events()
        logger.info(f"[API] ✅ Carregados {len(events)} eventos do manual_calendar.ics")
        return jsonify(events), 200
        
    except Exception as e:
        logger.error(f"[API] ❌ Erro ao carregar manual: {e}", exc_info=True)
        return jsonify([]), 500


@app.route('/api/calendar/save', methods=['POST'])
@api_login_required
def api_calendar_save():
    """
    POST /api/calendar/save
    
    Grava alterações em manual_calendar.ics e faz git commit + push
    """
    try:
        data = request.get_json()
        added = data.get('added', [])
        removed = data.get('removed', [])
        
        logger.info("=" * 80)
        logger.info(f"[API] 💾 POST /api/calendar/save - {len(added)} adições, {len(removed)} remoções")
        logger.info("=" * 80)
        
        editor = ManualEditorHandler()
        
        # Processar bloqueios (MANUAL-BLOCK)
        dates_block = [e['date'] for e in added if e['category'] == 'MANUAL-BLOCK']
        if dates_block:
            logger.info(f"[API] 🔒 Bloqueando {len(dates_block)} data(s)")
            editor.block_dates(dates_block)
        
        # Processar remoções (MANUAL-REMOVE)
        dates_remove = [e['date'] for e in added if e['category'] == 'MANUAL-REMOVE']
        if dates_remove:
            logger.info(f"[API] 🔓 Removendo eventos em {len(dates_remove)} data(s)")
            editor.remove_events(dates_remove)
        
        # Limpar eventos
        if removed:
            logger.info(f"[API] 🧹 Limpando {len(removed)} evento(s) manual(is)")
            editor.clear_events(removed)
        
        # Guardar manual_calendar.ics
        if not editor.save_manual_calendar():
            logger.error("[API] ❌ Erro ao guardar manual_calendar.ics")
            return jsonify({
                'success': False,
                'message': 'Erro ao guardar manual_calendar.ics'
            }), 500
        
        logger.info("[API] ✅ manual_calendar.ics guardado")
        
        # Git commit + push
        git_success = git_commit_push(
            ['manual_calendar.ics'],
            'manual_calendar.ics - Alterações editor manual [AUTO]'
        )
        
        logger.info("=" * 80)
        
        return jsonify({
            'success': True,
            'message': 'Alterações guardadas com sucesso',
            'events_added': len(added),
            'events_removed': len(removed),
            'git_synced': git_success,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"[API] ❌ Erro ao guardar: {e}", exc_info=True)
        logger.error("=" * 80)
        return jsonify({
            'success': False,
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """404 handler."""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(error):
    """500 handler."""
    logger.error(f"❌ Server error: {error}")
    return jsonify({'error': 'Server error'}), 500

# ============================================================================
# STARTUP
# ============================================================================

if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("🚀 Iniciando Rental Calendar Sync API (v1.3 - Com Git Automático)")
    logger.info("=" * 80)
    logger.info(f"REPO_PATH: {REPO_PATH}")
    logger.info(f"STATIC_PATH: {STATIC_PATH}")
    logger.info(f"TEMPLATES_PATH: {TEMPLATES_PATH}")
    logger.info("=" * 80)
    logger.info("✅ ENDPOINTS DISPONÍVEIS:")
    logger.info("  GET  /api/calendar/import   - Executa SYNC + Git push import_calendar.ics")
    logger.info("  GET  /api/calendar/manual   - Carrega manual_calendar.ics")
    logger.info("  POST /api/calendar/save     - Grava alterações + git push")
    logger.info("=" * 80)
    logger.info("")
    logger.info("🔴 FLUXO CRÍTICO COMPLETO IMPLEMENTADO:")
    logger.info("  /api/calendar/import → sync_calendars() → GIT PUSH → carrega .ics")
    logger.info("  (Sincroniza + grava no repositório ANTES de carregar)")
    logger.info("=" * 80)
    
    # Modo desenvolvimento vs produção
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 8000))
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        use_reloader=debug_mode
    )
