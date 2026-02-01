#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
auth.py - Gestão de Autenticação e Segurança

Versão: 1.0 Final
Data: 01 de fevereiro de 2026
Desenvolvido por: PBrandão
"""

from datetime import timedelta
from functools import wraps
from flask import session, redirect, url_for, jsonify

# ============================================================================
# CONFIGURAÇÃO - LÊ DE config.py (PRIORIDADE TOTAL)
# ============================================================================

try:
    from config import get_config
    cfg = get_config()
    ADMIN_USERNAME = cfg.ADMIN_USERNAME
    ADMIN_PASSWORD = cfg.ADMIN_PASSWORD
    USE_CONFIG = True
except (ImportError, AttributeError) as e:
    # Fallback APENAS se config.py não existir
    print(f"⚠️  Warning: config.py não carregado ({e})")
    print("   Usando credenciais de fallback...")
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = "Juju2323!"
    USE_CONFIG = False

# ============================================================================
# AUTH MANAGER - SIMPLIFICADO
# ============================================================================

class AuthManager:
    """
    Gestor de autenticação com sessões Flask.
    
    Modo: Sempre usa config.py se disponível
           Fallback para hardcoded se não
    
    Suporta session['user'] e session['authenticated'] para compatibilidade.
    """

    @staticmethod
    def authenticate(username: str, password: str) -> bool:
        """
        Valida credenciais contra config.ADMIN_USERNAME/ADMIN_PASSWORD
        
        Retorna: True se credenciais corretas, False caso contrário
        """
        return (username == ADMIN_USERNAME and password == ADMIN_PASSWORD)

    @staticmethod
    def login(username: str) -> None:
        """Define utilizador na sessão (suporta modo novo e compatível)."""
        
        # Novo modo (session['user'])
        session['user'] = username
        
        # Modo compatível (session['authenticated'] + session['username'])
        session['authenticated'] = True
        session['username'] = username
        
        # Configura sessão como permanente (7 dias por padrão)
        session.permanent = True

    @staticmethod
    def logout() -> None:
        """Remove utilizador da sessão."""
        session.pop('user', None)
        session.pop('authenticated', None)
        session.pop('username', None)

    @staticmethod
    def is_authenticated() -> bool:
        """
        Verifica se utilizador está autenticado.
        
        Suporta:
        - session['user'] (modo novo)
        - session['authenticated'] (modo compatível)
        """
        # Novo modo
        if 'user' in session and session['user'] is not None:
            return True
        
        # Modo compatível (antigo)
        if session.get('authenticated', False):
            return True
        
        return False

    @staticmethod
    def get_current_user() -> str:
        """Retorna utilizador atual."""
        # Novo modo
        if 'user' in session:
            return session.get('user')
        
        # Modo compatível (antigo)
        return session.get('username')

    @staticmethod
    def get_session_info() -> dict:
        """Retorna informação completa da sessão."""
        return {
            'authenticated': AuthManager.is_authenticated(),
            'user': AuthManager.get_current_user(),
            'mode': 'config' if USE_CONFIG else 'fallback'
        }


# ============================================================================
# DECORADORES
# ============================================================================

def login_required(view_func):
    """
    Decorator para proteger rotas HTML.
    Redireciona para login page se não autenticado.
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not AuthManager.is_authenticated():
            return redirect(url_for('login_page'))
        return view_func(*args, **kwargs)
    return wrapper


def api_login_required(view_func):
    """
    Decorator para proteger endpoints de API.
    Retorna JSON 401 se não autenticado.
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not AuthManager.is_authenticated():
            return jsonify({
                'status': 'error',
                'message': 'Unauthorized',
                'authenticated': False
            }), 401
        return view_func(*args, **kwargs)
    return wrapper


# ============================================================================
# INICIALIZAÇÃO - LOG DE INFORMAÇÃO
# ============================================================================

if __name__ != "__main__":
    # Apenas quando importado (não quando executado diretamente)
    print(f"✅ auth.py carregado (modo: {'config' if USE_CONFIG else 'fallback'})")
    print(f"   ADMIN_USERNAME: {ADMIN_USERNAME}")
    if not USE_CONFIG:
        print(f"   ADMIN_PASSWORD: {ADMIN_PASSWORD} (FALLBACK - Use config.py!)")
