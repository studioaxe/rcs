"""
auth.py - Gestão de autenticação e segurança
"""

from datetime import timedelta
from flask import session, redirect, url_for, jsonify
from functools import wraps

from config import get_config

cfg = get_config()


class AuthManager:
    """Gestor de autenticação baseada em sessão."""

    @staticmethod
    def is_authenticated() -> bool:
        """Retorna True se o utilizador estiver autenticado."""
        return session.get('authenticated', False)

    @staticmethod
    def authenticate(username: str, password: str) -> bool:
        """Valida credenciais contra as definidas na configuração."""
        return (
            username == cfg.ADMIN_USERNAME and
            password == cfg.ADMIN_PASSWORD
        )

    @staticmethod
    def login(username: str) -> None:
        """Marca a sessão como autenticada."""
        session['authenticated'] = True
        session['username'] = username
        session.permanent = True

    @staticmethod
    def logout() -> None:
        """Limpa sessão do utilizador."""
        session.clear()

    @staticmethod
    def get_session_info():
        """Informação básica da sessão."""
        return {
            'authenticated': AuthManager.is_authenticated(),
            'username': session.get('username')
        }


def login_required(view_func):
    """Decorator para proteger rotas HTML."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not AuthManager.is_authenticated():
            return redirect(url_for('login_page'))
        return view_func(*args, **kwargs)
    return wrapper


def api_login_required(view_func):
    """Decorator para proteger endpoints de API (retorna JSON 401)."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not AuthManager.is_authenticated():
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        return view_func(*args, **kwargs)
    return wrapper
