#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
main.py - Rental Calendar Sync - Flask API

Versão: 1.0 Final
Data: 01 de fevereiro de 2026
Desenvolvido por: PBrandão
"""

import os
import sys
import logging
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from flask import Flask, render_template, request, redirect, url_for, jsonify, session

sys.path.insert(0, str(Path(__file__).parent))
from auth import AuthManager, login_required, api_login_required
from sync import sync_calendars, convert_events_to_nights, apply_night_overlay_rules, REPO_DIR
from backend.notifier import EmailNotifier
from backend.ics import ICSHandler
from backend.manual_editor import ManualEditorHandler

# ✅ v2.1: Lógica de Deteção de Caminho para Aplicação (Render vs. Local)
# REPO_PATH é a raiz do repositório Git (para operações git)
# APP_ROOT_PATH é a raiz da aplicação Flask (onde estão templates, static, etc.)
REPO_PATH = Path(REPO_DIR)
APP_ROOT_PATH = REPO_PATH

# No ambiente Render, o código-fonte fica dentro de um subdiretório 'src'
if os.getenv('RENDER') == 'true':
    APP_ROOT_PATH = REPO_PATH / "src"

# Caminhos para Flask, baseados na raiz da aplicação
STATIC_PATH = APP_ROOT_PATH / "static"
TEMPLATES_PATH = APP_ROOT_PATH / "templates"

# Certificar que as pastas existem (importante para ambientes como Docker ou builds limpos)
STATIC_PATH.mkdir(exist_ok=True)
TEMPLATES_PATH.mkdir(exist_ok=True)

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # O log da app deve ficar na raiz do repositório, não na pasta 'src'
        logging.FileHandler(REPO_PATH / "app.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

logger.info(f"REPO_PATH (para Git): {REPO_PATH}")
logger.info(f"APP_ROOT_PATH (para Flask): {APP_ROOT_PATH}")
logger.info(f"STATIC_PATH: {STATIC_PATH}")
logger.info(f"TEMPLATES_PATH: {TEMPLATES_PATH}")

# Inicialização da App Flask com os caminhos corretos
app = Flask(__name__, static_folder=str(STATIC_PATH), template_folder=str(TEMPLATES_PATH))
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-prod')
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_SESSION_SECURE', 'False').lower() == 'true'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 7

notifier = EmailNotifier()

# ============================================================================
# ROTAS PÚBLICAS
# ============================================================================

@app.route('/', methods=['GET'])
def index():
    """Redireciona para editor manual de calendário se autenticado, senão para login."""
    if AuthManager.is_authenticated():
        return redirect(url_for('manual_editor_page'))
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
            logger.info(f'Login bem-sucedido: {username}')
            return redirect(url_for('manual_editor_page'))
        else:
            logger.warning(f'Tentativa de login falhou: {username}')
            return render_template('login.html', error='Credenciais inválidas'), 401
    
    return render_template('login.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout_page():
    """Logout e redireciona para login."""
    user = AuthManager.get_current_user()
    AuthManager.logout()
    logger.info(f'Logout: {user}')
    return redirect(url_for('login_page'))

# ============================================================================
# ROTAS PAGES (TEMPLATES)
# ============================================================================

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
# FUNÇÕES AUXILIARES
# ============================================================================

import base64
import requests

# ============================================================================
# FUNÇÕES AUXILIARES - GITHUB API
# ============================================================================

def get_github_file_sha(filepath: str) -> Optional[str]:
    """Obtém o SHA de um ficheiro no repositório via API do GitHub."""
    github_token = os.getenv('GITHUB_TOKEN')
    github_owner = os.getenv('GITHUB_OWNER')
    github_repo = os.getenv('GITHUB_REPO')
    
    api_url = f"https://api.github.com/repos/{github_owner}/{github_repo}/contents/{filepath}"
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            sha = response.json()['sha']
            logger.info(f"GIT API: SHA obtido para '{filepath}': {sha}")
            return sha
        elif response.status_code == 404:
            logger.warning(f"GIT API: Ficheiro '{filepath}' não encontrado no repositório. Será criado.")
            return None
        else:
            logger.error(f"GIT API: Erro ao obter SHA para '{filepath}'. Status: {response.status_code}, Resposta: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"GIT API: Exceção ao obter SHA para '{filepath}': {e}")
        return None

/*************  ✨ Windsurf Command 🌟  *************/
def update_github_file(filepath: str, commit_message: str) -> bool:
    """Lê um ficheiro local e atualiza-o no GitHub via API."""
    github_token = os.getenv('GITHUB_TOKEN')
    github_owner = os.getenv('GITHUB_OWNER')
    github_repo = os.getenv('GITHUB_REPO')

    # ✅ Correção v2.1: O ficheiro é lido a partir do REPO_PATH, que é a raiz do repositório.
    local_file_path = REPO_PATH / filepath
    
    if not local_file_path.exists():
        logger.error(f"GIT API: Ficheiro local '{local_file_path}' não encontrado para upload.")
        return False

    try:
        with open(local_file_path, 'rb') as f:
            content_bytes = f.read()
    except FileNotFoundError:
        logger.error(f"GIT API: Ficheiro local '{local_file_path}' não encontrado para upload.")
        return False

    with open(local_file_path, 'rb') as f:
        content_bytes = f.read()
    
    content_base64 = base64.b64encode(content_bytes).decode('utf-8')
    
    sha = get_github_file_sha(filepath)
    
    api_url = f"https://api.github.com/repos/{github_owner}/{github_repo}/contents/{filepath}"
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    data = {
        'message': commit_message,
        'content': content_base64,
        'branch': 'main'
    }
    if sha:
        data['sha'] = sha

    try:
        response = requests.put(api_url, headers=headers, json=data, timeout=30)
        if response.status_code in [200, 201]:
            logger.info(f"GIT API: Ficheiro '{filepath}' atualizado/criado com sucesso.")
            return True
        else:
            logger.error(f"GIT API: Erro ao atualizar ficheiro '{filepath}'. Status: {response.status_code}, Resposta: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"GIT API: Exceção ao atualizar ficheiro '{filepath}': {e}")
        return False
/*******  d9e42a77-2f20-4a85-993a-3d4bd59a14ad  *******/


# ============================================================================
# API - SESSION
# ============================================================================

@app.route('/api/session', methods=['GET'])
def api_session():
    """Retorna informação de sessão atual."""
    session_info = AuthManager.get_session_info()
    return jsonify(status='success', session=session_info)

from functools import wraps

# Chave de API para proteger endpoints de automação
API_SECRET_KEY = os.getenv('API_SECRET_KEY')

def api_key_required(f):
    """Decorator para exigir chave de API em endpoints de automação."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not API_SECRET_KEY:
            logger.critical("API_SECRET_KEY não está configurada no ambiente!")
            return jsonify(error="Configuração de segurança do servidor incompleta"), 500
            
        key = request.headers.get('X-API-Key')
        if key != API_SECRET_KEY:
            logger.warning(f"Acesso negado ao endpoint de API. Chave: {'presente' if key else 'ausente'}")
            return jsonify(error="Acesso não autorizado"), 401
        
        return f(*args, **kwargs)
    return decorated_function

# ... (manter o resto do ficheiro) ...

# ============================================================================
# API - SYNC
# ============================================================================

@app.route('/api/sync', methods=['POST'])
@api_key_required
def api_sync():
    """Força sincronização imediata, usado pela automação do GitHub."""
    try:
        # A automação deve sempre descarregar dados frescos
        force_download = request.args.get('force', 'true').lower() == 'true'
        source = request.args.get('source', 'desconhecida')

        logger.info('='*80)
        logger.info(f"API: Sincronização iniciada (via API Key) - Fonte: {source}")
        logger.info('='*80)
        
        success = sync_calendars(force_download=force_download)
        
        if success:
            logger.info("API: Sincronização local concluída. Atualizando GitHub...")
            update_github_file('import_calendar.ics', f'Auto-sync: import_calendar.ics (Fonte: {source})')
            update_github_file('master_calendar.ics', f'Auto-sync: master_calendar.ics (Fonte: {source})')
            
            return jsonify(
                status='success',
                message='Sincronização completada e ficheiros atualizados no GitHub.',
                timestamp=datetime.now().isoformat()
            ), 200
        else:
            logger.error('='*80)
            logger.error('API: Sincronização falhou')
            logger.error('='*80)
            return jsonify(
                status='error',
                message='Erro na sincronização',
                timestamp=datetime.now().isoformat()
            ), 500
            
    except Exception as e:
        logger.error('='*80)
        logger.error(f'API: Erro na sincronização: {e}', exc_info=True)
        logger.error('='*80)
        notifier.send_error(f'API sync error: {str(e)}')
        return jsonify(
            status='error',
            message=str(e),
            timestamp=datetime.now().isoformat()
        ), 500

@app.route('/api/sync-manual', methods=['POST'])
@api_login_required
def api_sync_manual():
    """Força sincronização imediata a partir da UI (requer login)."""
    try:
        user = AuthManager.get_current_user()
        should_notify = request.args.get('notify', 'true').lower() == 'true'
        
        logger.info('='*80)
        logger.info(f"API: Sincronização MANUAL iniciada por utilizador: {user} | Notificar: {should_notify}")
        logger.info('='*80)
        
        # Forçar download para garantir que os calendários externos estão atualizados
        success = sync_calendars(force_download=True)
        
        if success:
            logger.info("API: Sincronização manual concluída. Atualizando GitHub...")
            update_github_file('import_calendar.ics', f'Manual sync: import_calendar.ics (User: {user})')
            update_github_file('master_calendar.ics', f'Manual sync: master_calendar.ics (User: {user})')
            
            if should_notify:
                logger.info("Enviando notificação de sucesso...")
                notifier.send_success(total_events=0, reserved_count=0)
            
            return jsonify(
                status='success',
                message='Sincronização completada e ficheiros atualizados no GitHub.',
                timestamp=datetime.now().isoformat()
            ), 200
        else:
            logger.error('='*80)
            logger.error('API: Sincronização manual falhou')
            logger.error('='*80)
            return jsonify(
                status='error',
                message='Erro na sincronização',
                timestamp=datetime.now().isoformat()
            ), 500
            
    except Exception as e:
        logger.error('='*80)
        logger.error(f'API: Erro na sincronização manual: {e}', exc_info=True)
        logger.error('='*80)
        notifier.send_error(f'API sync error: {str(e)}')
        return jsonify(
            status='error',
            message=str(e),
            timestamp=datetime.now().isoformat()
        ), 500

# ============================================================================
# API - CALENDAR (IMPORT/MANUAL/SAVE)
# ============================================================================

@app.route('/api/calendar/import', methods=['GET'])
@api_login_required
def api_calendar_import():
    """GET /api/calendar/import - FLUXO CRÍTICO COMPLETO"""
    try:
        logger.info('='*80)
        logger.info('API: GET /api/calendar/import')
        logger.info('API: EXECUTANDO SYNC.PY + GIT (CRÍTICO)...')
        logger.info('='*80)
        
        logger.info('API: Iniciando sync_calendars()...')
        sync_start = datetime.now()
        try:
            sync_success = sync_calendars(force_download=True)
            sync_end = datetime.now()
            sync_duration = (sync_end - sync_start).total_seconds()
            if sync_success:
                logger.info(f'API: Sync.py concluído com SUCESSO ({sync_duration:.2f}s)')
            else:
                logger.warning(f'API: Sync.py retornou False ({sync_duration:.2f}s)')
        except Exception as sync_error:
            logger.error(f'API: Erro durante sync.py: {sync_error}', exc_info=True)
            logger.warning('API: Continuando mesmo com erro...')
        
        logger.info('API: Sincronização local concluída. Atualizando GitHub...')
        update_github_file('import_calendar.ics', 'Calendar import: import_calendar.ics')
        update_github_file('master_calendar.ics', 'Calendar import: master_calendar.ics')
        
        logger.info('API: Carregando import_calendar.ics ATUALIZADO...')
        editor = ManualEditorHandler()
        events = editor.load_import_events()
        logger.info(f'API: Carregados {len(events)} eventos do import_calendar.ics')
        logger.info('='*80)
        
        return jsonify(events), 200
        
    except Exception as e:
        logger.error('='*80)
        logger.error(f'API: ERRO ao carregar import: {e}', exc_info=True)
        logger.error('='*80)
        return jsonify(error=str(e)), 500

@app.route('/api/calendar/manual', methods=['GET'])
@api_login_required
def api_calendar_manual():
    """GET /api/calendar/manual - Carrega eventos do manual_calendar.ics"""
    try:
        logger.info('API: GET /api/calendar/manual')
        editor = ManualEditorHandler()
        events = editor.load_manual_events()
        logger.info(f'API: Carregados {len(events)} eventos do manual_calendar.ics')
        return jsonify(events), 200
    except Exception as e:
        logger.error(f'API: Erro ao carregar manual: {e}', exc_info=True)
        return jsonify(error=str(e)), 500

@app.route('/api/calendar/save', methods=['POST'])
@api_login_required
def api_calendar_save():
    """POST /api/calendar/save - Grava alterações em manual_calendar.ics"""
    try:
        data = request.get_json()
        added = data.get('added', [])
        removed = data.get('removed', [])
        
        logger.info('='*80)
        logger.info(f'API: POST /api/calendar/save - {len(added)} adições, {len(removed)} remoções')
        logger.info('='*80)
        
        editor = ManualEditorHandler()
        
        block_intervals = [e for e in added if e['category'] == 'MANUAL-BLOCK' and 'startDate' in e]
        block_dates_single = [e['date'] for e in added if e['category'] == 'MANUAL-BLOCK' and 'date' in e]
        
        if block_intervals:
            logger.info(f'API: Bloqueando {len(block_intervals)} intervalo(s)')
            for interval in block_intervals:
                editor.block_date_range(interval['startDate'], interval['endDate'])
        
        if block_dates_single:
            logger.info(f'API: Bloqueando {len(block_dates_single)} data(s) individual(is)')
            editor.block_dates(block_dates_single)
        
        remove_intervals = [e for e in added if e['category'] == 'MANUAL-REMOVE' and 'startDate' in e]
        remove_dates_single = [e['date'] for e in added if e['category'] == 'MANUAL-REMOVE' and 'date' in e]
        
        if remove_intervals:
            logger.info(f'API: Removendo {len(remove_intervals)} intervalo(s)')
            for interval in remove_intervals:
                editor.remove_event_range(interval['startDate'], interval['endDate'])
        
        if remove_dates_single:
            logger.info(f'API: Removendo eventos em {len(remove_dates_single)} data(s) individual(is)')
            editor.remove_events(remove_dates_single)
        
        if removed:
            logger.info(f'API: Limpando {len(removed)} eventos manuais')
            editor.clear_events(removed)
        
        if not editor.save_manual_calendar():
            logger.error('API: Erro ao guardar manual_calendar.ics')
            return jsonify(success=False, message='Erro ao guardar manual_calendar.ics'), 500
        
        logger.info("API: manual_calendar.ics guardado localmente. Atualizando no GitHub...")
        user = AuthManager.get_current_user() or 'unknown'
        git_success_manual = update_github_file('manual_calendar.ics', f'Editor manual: {user}')

        logger.info("API: Re-sincronizar para atualizar master_calendar.ics...")
        sync_success = sync_calendars(force_download=False)
        if not sync_success:
            logger.error('API: Erro ao re-sincronizar calendários após guardar alterações manuais.')
            # Nota: Mesmo com este erro, o manual_calendar.ics já foi enviado para o GitHub.
        
        logger.info("API: Sincronização local concluída. Atualizando master no GitHub...")
        git_success_master = update_github_file('master_calendar.ics', f'Update master por editor manual (User: {user})')

        logger.info('='*80)
        
        return jsonify(
            success=True,
            message='Alterações guardadas e calendários sincronizados com sucesso no GitHub.',
            events_added=len(added),
            events_removed=len(removed),
            git_synced=git_success_manual and git_success_master,
            sync_success=sync_success,
            timestamp=datetime.now().isoformat()
        ), 200
        
    except Exception as e:
        logger.error('='*80)
        logger.error(f'API: Erro ao guardar: {e}', exc_info=True)
        logger.error('='*80)
        return jsonify(
            success=False,
            message=str(e),
            timestamp=datetime.now().isoformat()
        ), 500

# ============================================================================
# API - CALENDAR NIGHTS
# ============================================================================

@app.route('/api/calendar/nights', methods=['GET'])
@api_login_required
def api_calendar_nights():
    """GET /api/calendar/nights - NOITES consolidadas"""
    try:
        logger.info('API: GET /api/calendar/nights')
        
        import_events = ICSHandler.read_ics_file('import_calendar.ics') or []
        manual_events = ICSHandler.read_ics_file('manual_calendar.ics') or []
        logger.info(f'API: Carregados {len(import_events)} eventos (import) + {len(manual_events)} eventos (manual)')
        
        import_nights = convert_events_to_nights(import_events)
        manual_nights = convert_events_to_nights(manual_events)
        
        final_nights = apply_night_overlay_rules(import_nights, manual_nights)
        logger.info(f'API: {len(final_nights)} noites finais')
        
        COLORMAP = {
            'RESERVATION': 'ff0000',
            'PREP-TIME': 'ffaa00',
            'MANUAL-BLOCK': '00ff00',
            'MANUAL-REMOVE': 'ffff00',
            'AVAILABLE': '4dd9ff'
        }
        
        nights_with_colors = {}
        for night_date, night_data in final_nights.items():
            category = night_data['category']
            color = COLORMAP.get(category, '4dd9ff')
            nights_with_colors[night_date] = {
                'category': category,
                'color': color,
                'description': night_data.get('description', ''),
                'uid': night_data.get('uid', '')
            }
        
        return jsonify(
            success=True,
            data=nights_with_colors,
            count=len(nights_with_colors),
            timestamp=datetime.now().isoformat()
        ), 200
        
    except Exception as e:
        logger.error(f'API: Erro ao converter noites: {e}', exc_info=True)
        return jsonify(
            success=False,
            error=str(e),
            timestamp=datetime.now().isoformat()
        ), 500

# ============================================================================
# API - EVENTS
# ============================================================================

@app.route('/api/events', methods=['GET'])
@api_login_required
def api_events():
    """GET /api/events - Retorna eventos para renderização no calendário"""
    try:
        logger.info('API: GET /api/events')
        
        import_events = ICSHandler.read_ics_file('import_calendar.ics') or []
        manual_events = ICSHandler.read_ics_file('manual_calendar.ics') or []
        logger.info(f'API: Carregados {len(import_events)} eventos (import) + {len(manual_events)} eventos (manual)')
        
        import_nights = convert_events_to_nights(import_events)
        manual_nights = convert_events_to_nights(manual_events)
        
        final_nights = apply_night_overlay_rules(import_nights, manual_nights)
        logger.info(f'API: {len(final_nights)} noites finais')
        
        COLORMAP = {
            'RESERVATION': '#ff0000',
            'PREP-TIME': '#ffaa00',
            'MANUAL-BLOCK': '#00ff00',
            'MANUAL-REMOVE': '#ffff00',
            'AVAILABLE': '#4dd9ff'
        }
        
        events_list = []
        processed = set()
        
        all_events = import_events + manual_events
        
        for event in all_events:
            event_id = (
                event.get('dtstart'),
                event.get('dtend'),
                event.get('categories', 'AVAILABLE')
            )
            
            if event_id in processed:
                continue
            
            processed.add(event_id)
            
            dtstart = event.get('dtstart')
            dtend = event.get('dtend')
            category = event.get('categories', 'AVAILABLE')
            summary = event.get('summary', 'Event')
            
            if isinstance(dtstart, str):
                dtstart = f"{dtstart[:4]}-{dtstart[4:6]}-{dtstart[6:8]}"
            
            if isinstance(dtend, str):
                dtend = f"{dtend[:4]}-{dtend[4:6]}-{dtend[6:8]}"
            
            color = COLORMAP.get(category, '#4dd9ff')
            
            events_list.append({
                'summary': summary,
                'start': dtstart,
                'end': dtend,
                'type': category,
                'color': color
            })
        
        logger.info(f'API: Retornando {len(events_list)} eventos formatados')
        
        return jsonify(
            success=True,
            data=events_list,
            count=len(events_list),
            timestamp=datetime.now().isoformat()
        ), 200
        
    except Exception as e:
        logger.error(f'API: Erro ao formatar eventos: {e}', exc_info=True)
        return jsonify(
            success=False,
            error=str(e),
            timestamp=datetime.now().isoformat()
        ), 500

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found_error(error):
    """404 handler."""
    return jsonify(error='Not found'), 404

@app.errorhandler(500)
def server_error(error):
    """500 handler."""
    logger.error(f'Server error: {error}')
    return jsonify(error='Server error'), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    logger.info('='*80)
    logger.info('Iniciando Rental Calendar Sync API v1.5')
    logger.info('='*80)
    logger.info(f'REPO_PATH: {REPO_PATH}')
    logger.info(f'STATIC_PATH: {STATIC_PATH}')
    logger.info(f'TEMPLATES_PATH: {TEMPLATES_PATH}')
    logger.info('='*80)
    logger.info('ENDPOINTS DISPONÍVEIS:')
    logger.info('  GET  /api/calendar/import - Executa SYNC + Git push')
    logger.info('  GET  /api/calendar/manual - Carrega manual_calendar.ics')
    logger.info('  POST /api/calendar/save   - Grava alterações + git push')
    logger.info('  GET  /api/calendar/nights - Retorna NOITES consolidadas')
    logger.info('  GET  /api/events          - Eventos para barras visuais')
    logger.info('='*80)
    
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 8000))
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=debug_mode)
