#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
app.py - Flask Web Application
Rental Calendar Sync - Web Interface

Versão: 1.0
Data: 19 de Janeiro de 2026
Desenvolvido por: PBrandão
"""

import os
import subprocess
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Import modules
from auth import AuthManager, login_required, api_login_required
from backend.calendar_handler import CalendarHandler
from backend.git_sync import GitSync

# Load environment variables
load_dotenv()

# ============================================================================
# FLASK APP INITIALIZATION
# ============================================================================

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'rental-calendar-sync-secret-key-2026')
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

CORS(app)

# Initialize handlers
calendar_handler = CalendarHandler()
git_sync = GitSync()

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Login page route."""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        if AuthManager.authenticate(username, password):
            AuthManager.login(username)
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Credenciais inválidas'), 401
    
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    """Logout route."""
    AuthManager.logout()
    return redirect(url_for('login_page'))

# ============================================================================
# MAIN ROUTES
# ============================================================================

@app.route('/')
def index():
    """Root route - redirect to dashboard if authenticated, else to login."""
    if AuthManager.is_authenticated():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login_page'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard page."""
    user = AuthManager.get_current_user()
    return render_template('dashboard.html', user=user)

@app.route('/manual-editor')
@login_required
def manual_editor():
    """Manual editor page."""
    user = AuthManager.get_current_user()
    return render_template('manual_editor.html', user=user)

# ============================================================================
# API ENDPOINTS - CALENDAR OPERATIONS
# ============================================================================

@app.route('/api/calendar/sync', methods=['POST'])
@api_login_required
def api_sync_calendar():
    """
    Force sync and update master_calendar.ics
    Endpoint for Semi-Auto (2.2) workflow
    """
    try:
        # Run sync.py
        result = subprocess.run(
            ['python', 'backend/sync.py'],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            # Auto commit and push
            git_sync.commit_and_push(
                'master_calendar.ics',
                '[AUTO] Semi-Auto Sync - Master Calendar Updated'
            )
            
            return jsonify({
                'status': 'success',
                'message': 'Calendário sincronizado com sucesso',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Erro ao sincronizar calendário',
                'details': result.stderr
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/calendar/load', methods=['GET'])
@api_login_required
def api_load_calendar():
    """
    Load import_calendar.ics and manual_calendar.ics
    Returns merged events data for frontend
    """
    try:
        # Load calendars
        import_events = calendar_handler.load_calendar('import_calendar.ics')
        manual_events = calendar_handler.load_calendar('manual_calendar.ics')
        
        # Merge and prepare for frontend
        merged_data = calendar_handler.merge_calendars_for_ui(
            import_events,
            manual_events
        )
        
        return jsonify({
            'status': 'success',
            'events': merged_data,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/calendar/events', methods=['GET'])
@api_login_required
def api_get_events():
    """Get events for specific date range."""
    try:
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        
        if not start_date or not end_date:
            return jsonify({
                'status': 'error',
                'message': 'Missing date parameters'
            }), 400
        
        # Load and filter events
        import_events = calendar_handler.load_calendar('import_calendar.ics')
        manual_events = calendar_handler.load_calendar('manual_calendar.ics')
        
        events = calendar_handler.get_events_in_range(
            import_events + manual_events,
            start_date,
            end_date
        )
        
        return jsonify({
            'status': 'success',
            'events': events
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ============================================================================
# API ENDPOINTS - MANUAL CALENDAR OPERATIONS
# ============================================================================

@app.route('/api/manual/block-date', methods=['POST'])
@api_login_required
def api_block_date():
    """
    Add MANUAL-BLOCK event to manual_calendar.ics
    Equivalent to 🔒 Bloquear Data button
    """
    try:
        data = request.get_json()
        dates = data.get('dates', [])  # Array of dates
        description = data.get('description', 'Data Bloqueada Manualmente')
        
        if not dates:
            return jsonify({
                'status': 'error',
                'message': 'No dates provided'
            }), 400
        
        # Add events to manual calendar
        calendar_handler.add_manual_events(
            dates,
            'MANUAL-BLOCK',
            description
        )
        
        return jsonify({
            'status': 'success',
            'message': f'{len(dates)} data(s) bloqueada(s)',
            'dates': dates
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/manual/remove-event', methods=['POST'])
@api_login_required
def api_remove_event():
    """
    Add MANUAL-REMOVE event to manual_calendar.ics
    Equivalent to 🔓 Remover Evento button
    """
    try:
        data = request.get_json()
        dates = data.get('dates', [])
        description = data.get('description', 'Data Desbloqueada Manualmente')
        
        if not dates:
            return jsonify({
                'status': 'error',
                'message': 'No dates provided'
            }), 400
        
        # Add events to manual calendar
        calendar_handler.add_manual_events(
            dates,
            'MANUAL-REMOVE',
            description
        )
        
        return jsonify({
            'status': 'success',
            'message': f'{len(dates)} data(s) marcada(s) para remover',
            'dates': dates
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/manual/clear-event', methods=['POST'])
@api_login_required
def api_clear_event():
    """
    Clear event from manual_calendar.ics
    Equivalent to 🧹 Limpar Evento Manual button
    """
    try:
        data = request.get_json()
        dates = data.get('dates', [])
        
        if not dates:
            return jsonify({
                'status': 'error',
                'message': 'No dates provided'
            }), 400
        
        # Remove events from manual calendar
        calendar_handler.remove_manual_events(dates)
        
        return jsonify({
            'status': 'success',
            'message': f'{len(dates)} evento(s) removido(s)',
            'dates': dates
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/manual/save', methods=['POST'])
@api_login_required
def api_save_manual_calendar():
    """
    Save manual_calendar.ics and commit to git
    Equivalent to 💾 Aplicar & Guardar button
    """
    try:
        # Run sync.py to merge calendars
        sync_result = subprocess.run(
            ['python', 'backend/sync.py'],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if sync_result.returncode != 0:
            return jsonify({
                'status': 'error',
                'message': 'Erro ao sincronizar calendários',
                'details': sync_result.stderr
            }), 500
        
        # Commit and push
        git_sync.commit_and_push(
            ['manual_calendar.ics', 'master_calendar.ics'],
            '[MANUAL] Manual Calendar Updated - Master Calendar Merged'
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Calendário manual salvo e sincronizado',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ============================================================================
# API ENDPOINTS - SESSION
# ============================================================================

@app.route('/api/session', methods=['GET'])
def api_session_info():
    """Get current session information."""
    return jsonify(AuthManager.get_session_info())

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'status': 'error',
        'message': 'Not found'
    }), 404

@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors."""
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Development mode
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('FLASK_PORT', 8000)),
        debug=os.getenv('FLASK_ENV', 'development') == 'development'
    )
