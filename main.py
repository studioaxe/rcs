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
from typing import Dict, List, Tuple
from flask import Flask, render_template, request, redirect, url_for, jsonify, session

sys.path.insert(0, str(Path(__file__).parent))
from auth import AuthManager, login_required, api_login_required
from sync import sync_calendars, convert_events_to_nights, apply_night_overlay_rules
from backend.notifier import EmailNotifier
from backend.ics import ICSHandler
from backend.manual_editor import ManualEditorHandler

REPO_PATH = Path(__file__).parent
STATIC_PATH = REPO_PATH / "static"
TEMPLATES_PATH = REPO_PATH / "templates"

STATIC_PATH.mkdir(exist_ok=True)
TEMPLATES_PATH.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(REPO_PATH / "app.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

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

def git_commit_push(files: List[str], message: str) -> bool:
    """Faz git add, commit e push para ficheiros específicos."""
    try:
        logger.info(f'GIT: Git add, commit, push para {len(files)} ficheiros')
        
        # CONFIGURAR GIT IDENTITY ANTES DE QUALQUER OPERAÇÃO
        logger.info('GIT: Configurando identidade Git...')
        subprocess.run(
            ['git', 'config', '--global', 'user.name', 'Rental Calendar Sync Bot'],
            cwd=str(REPO_PATH),
            check=True,
            capture_output=True,
            timeout=10
        )
        subprocess.run(
            ['git', 'config', '--global', 'user.email', 'noreply@render.com'],
            cwd=str(REPO_PATH),
            check=True,
            capture_output=True,
            timeout=10
        )
        logger.info('GIT: Identidade configurada')
        
        # Git add
        for file in files:
            logger.info(f'GIT: git add {file}')
            subprocess.run(
                ['git', 'add', file],
                cwd=str(REPO_PATH),
                check=True,
                capture_output=True,
                timeout=30
            )
        
        # Git commit
        logger.info(f'GIT: git commit -m "{message}"')
        try:
            result = subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=str(REPO_PATH),
                check=True,
                capture_output=True,
                timeout=30
            )
            logger.info('GIT: Commit concluído')
        except subprocess.CalledProcessError as e:
            if 'nothing to commit' in e.stderr.decode():
                logger.info('GIT: Sem mudanças para commit (working tree clean)')
                return True
            else:
                logger.error(f'GIT: Commit falhou: {e.stderr.decode()}')
                return False
        
        # Git push
        logger.info('GIT: git push')
        subprocess.run(
            ['git', 'push'],
            cwd=str(REPO_PATH),
            check=True,
            capture_output=True,
            timeout=60
        )
        logger.info('GIT: Push concluído')
        return True
        
    except subprocess.TimeoutExpired:
        logger.error('GIT: Timeout na operação git')
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f'GIT: Git error: {e.stderr.decode() if e.stderr else str(e)}')
        return False
    except Exception as e:
        logger.error(f'GIT: Erro inesperado: {e}', exc_info=True)
        return False

# ============================================================================
# API - SESSION
# ============================================================================

@app.route('/api/session', methods=['GET'])
def api_session():
    """Retorna informação de sessão atual."""
    session_info = AuthManager.get_session_info()
    return jsonify(status='success', session=session_info)

# ============================================================================
# API - SYNC
# ============================================================================

@app.route('/api/sync', methods=['POST'])
@api_login_required
def api_sync():
    """Força sincronização imediata."""
    try:
        should_notify = request.args.get('notify', 'true').lower() == 'true'
        
        logger.info('='*80)
        logger.info(f"API: Sincronização iniciada (Manual) - Notificar: {should_notify}")
        logger.info('='*80)
        
        success = sync_calendars()
        
        if success:
            logger.info('='*80)
            logger.info('API: Sincronização concluída com sucesso')
            logger.info('='*80)
            
            git_commit_push(
                ['import_calendar.ics', 'master_calendar.ics'],
                'import_calendar.ics + master_calendar.ics - Sincronização automática (AUTO)'
            )
            
            if should_notify:
                logger.info("Enviando notificação de sucesso...")
                notifier.send_success(total_events=0, reserved_count=0)
            else:
                logger.info("Omitindo notificação de sucesso (notify=false).")
            
            return jsonify(
                status='success',
                message='Sincronização completada com sucesso',
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
        logger.error(f'API: Erro na sincronização: {e}')
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
            sync_success = sync_calendars()
            sync_end = datetime.now()
            sync_duration = (sync_end - sync_start).total_seconds()
            if sync_success:
                logger.info(f'API: Sync.py concluído com SUCESSO ({sync_duration:.2f}s)')
            else:
                logger.warning(f'API: Sync.py retornou False ({sync_duration:.2f}s)')
        except Exception as sync_error:
            logger.error(f'API: Erro durante sync.py: {sync_error}', exc_info=True)
            logger.warning('API: Continuando mesmo com erro...')
        
        logger.info('API: Git commit + push import_calendar.ics, master_calendar.ics')
        git_success = git_commit_push(
            ['import_calendar.ics', 'master_calendar.ics'],
            'import_calendar.ics + master_calendar.ics - Sincronização automática (AUTO)'
        )
        
        if git_success:
            logger.info('API: Git commit + push concluído')
        else:
            logger.warning('API: Git commit + push falhou (continuando)')
        
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
    """POST /api/calendar/save - Grava alterações em manual_calendar.ics
    
    Suporta:
    - Intervalo único: {startDate: '2026-02-25', endDate: '2026-02-28', category: 'MANUAL-BLOCK'}
    - Data individual: {date: '2026-02-25', category: 'MANUAL-BLOCK'} [compatibilidade]
    """
    try:
        data = request.get_json()
        added = data.get('added', [])
        removed = data.get('removed', [])
        
        logger.info('='*80)
        logger.info(f'API: POST /api/calendar/save - {len(added)} adições, {len(removed)} remoções')
        logger.info('='*80)
        
        editor = ManualEditorHandler()
        
        # Processar bloqueios MANUAL-BLOCK (suporta intervalos e datas individuais)
        block_intervals = [e for e in added if e['category'] == 'MANUAL-BLOCK' and 'startDate' in e]
        block_dates_single = [e['date'] for e in added if e['category'] == 'MANUAL-BLOCK' and 'date' in e]
        
        if block_intervals:
            logger.info(f'API: Bloqueando {len(block_intervals)} intervalo(s)')
            for interval in block_intervals:
                editor.block_date_range(interval['startDate'], interval['endDate'])
        
        if block_dates_single:
            logger.info(f'API: Bloqueando {len(block_dates_single)} data(s) individual(is)')
            editor.block_dates(block_dates_single)
        
        # Processar remoções MANUAL-REMOVE (suporta intervalos e datas individuais)
        remove_intervals = [e for e in added if e['category'] == 'MANUAL-REMOVE' and 'startDate' in e]
        remove_dates_single = [e['date'] for e in added if e['category'] == 'MANUAL-REMOVE' and 'date' in e]
        
        if remove_intervals:
            logger.info(f'API: Removendo {len(remove_intervals)} intervalo(s)')
            for interval in remove_intervals:
                editor.remove_event_range(interval['startDate'], interval['endDate'])
        
        if remove_dates_single:
            logger.info(f'API: Removendo eventos em {len(remove_dates_single)} data(s) individual(is)')
            editor.remove_events(remove_dates_single)
        
        # Limpar eventos
        if removed:
            logger.info(f'API: Limpando {len(removed)} eventos manuais')
            editor.clear_events(removed)
        
        if not editor.save_manual_calendar():
            logger.error('API: Erro ao guardar manual_calendar.ics')
            return jsonify(success=False, message='Erro ao guardar manual_calendar.ics'), 500
        
        logger.info('API: manual_calendar.ics guardado')
        
        # Git commit + push
        git_success = git_commit_push(
            ['manual_calendar.ics'],
            'manual_calendar.ics - Alterações (editor manual) (AUTO)'
        )
        
        logger.info('='*80)
        
        return jsonify(
            success=True,
            message='Alterações guardadas com sucesso',
            events_added=len(added),
            events_removed=len(removed),
            git_synced=git_success,
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
# API - CALENDAR NIGHTS (COMPATIBILIDADE v1.4)
# ============================================================================

@app.route('/api/calendar/nights', methods=['GET'])
@api_login_required
def api_calendar_nights():
    """GET /api/calendar/nights - NOITES consolidadas (v1.4 compatível)"""
    try:
        logger.info('API: GET /api/calendar/nights')
        
        # Carregar eventos
        import_events = ICSHandler.read_ics_file('import_calendar.ics') or []
        manual_events = ICSHandler.read_ics_file('manual_calendar.ics') or []
        logger.info(f'API: Carregados {len(import_events)} eventos (import) + {len(manual_events)} eventos (manual)')
        
        # Converter para noites
        import_nights = convert_events_to_nights(import_events)
        manual_nights = convert_events_to_nights(manual_events)
        
        # Aplicar regras de sobrecarga
        final_nights = apply_night_overlay_rules(import_nights, manual_nights)
        logger.info(f'API: {len(final_nights)} noites finais')
        
        # Mapear cores
        COLORMAP = {
            'RESERVATION': 'ff0000',      # Vermelho
            'PREP-TIME': 'ffaa00',        # Laranja
            'MANUAL-BLOCK': '00ff00',     # Verde Neon
            'MANUAL-REMOVE': 'ffff00',    # Amarelo
            'AVAILABLE': '4dd9ff'         # Azul Claro
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
# API - EVENTS (NOVO EM v1.5 - PARA FRONTEND)
# ============================================================================

@app.route('/api/events', methods=['GET'])
@api_login_required
def api_events():
    """GET /api/events - Retorna eventos para renderização de barras no calendário
    
    Formato de retorno (compatível com barras visuais):
    [
        {
            "summary": "Reserva VRBO",
            "start": "2026-02-13",
            "end": "2026-02-17",
            "type": "RESERVATION",
            "color": "#ff0000"
        },
        ...
    ]
    """
    try:
        logger.info('API: GET /api/events (NOVO v1.5)')
        
        # Carregar eventos
        import_events = ICSHandler.read_ics_file('import_calendar.ics') or []
        manual_events = ICSHandler.read_ics_file('manual_calendar.ics') or []
        logger.info(f'API: Carregados {len(import_events)} eventos (import) + {len(manual_events)} eventos (manual)')
        
        # Converter para noites
        import_nights = convert_events_to_nights(import_events)
        manual_nights = convert_events_to_nights(manual_events)
        
        # Aplicar regras de sobrecarga
        final_nights = apply_night_overlay_rules(import_nights, manual_nights)
        logger.info(f'API: {len(final_nights)} noites finais')
        
        # Mapear cores
        COLORMAP = {
            'RESERVATION': '#ff0000',      # Vermelho
            'PREP-TIME': '#ffaa00',        # Laranja
            'MANUAL-BLOCK': '#00ff00',     # Verde Neon
            'MANUAL-REMOVE': '#ffff00',    # Amarelo
            'AVAILABLE': '#4dd9ff'         # Azul Claro
        }
        
        # Agrupar noites por eventos (start, end, type)
        # Percorrer eventos originais para reconstruir intervalos
        events_list = []
        processed = set()
        
        # Processar eventos originais (import + manual)
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
                # Formato string YYYYMMDD
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
    logger.info('  GET  /api/events          - ✅ NOVO v1.5: Eventos para barras visuais')
    logger.info('='*80)
    
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 8000))
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=debug_mode)
