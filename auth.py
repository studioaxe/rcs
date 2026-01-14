#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auth.py - Gestão de Autenticação e Segurança
Versão: 3.2.4 CONSOLIDADA
Data: 13 de Janeiro de 2026

Consolida funcionalidades de:
- old-auth.py (usa config.py com ADMIN_USERNAME e ADMIN_PASSWORD)
- auth.py (usa USERS hardcoded)

Prioridade:
1. Se config.py tem ADMIN_USERNAME/ADMIN_PASSWORD → usa config
2. Se não → usa USERS hardcoded (fallback desenvolvimento)
3. Suporta session['authenticated'] (antigo) e session['user'] (novo)
"""

from datetime import timedelta
from functools import wraps
from flask import session, redirect, url_for, jsonify

# ============================================================================
# CONFIGURAÇÃO - TENTA CARREGAR CONFIG, SE FALHAR USA HARDCODED
# ============================================================================

try:
    from config import get_config
    cfg = get_config()
    ADMIN_USERNAME = cfg.ADMIN_USERNAME
    ADMIN_PASSWORD = cfg.ADMIN_PASSWORD
    USE_CONFIG = True
except (ImportError, AttributeError):
    # Fallback para desenvolvimento se config.py não existir ou não tiver atributos
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = "password123"
    USE_CONFIG = False

# ============================================================================
# CREDENCIAIS ALTERNATIVAS (Para desenvolvimento/testes)
# Usadas se config.py não estiver disponível
# ============================================================================

USERS = {
    "admin": "password123",
    "user": "user123",
    ADMIN_USERNAME: ADMIN_PASSWORD  # Suporta credenciais do config também
}

# ============================================================================
# AUTH MANAGER - CONSOLIDADO
# ============================================================================

class AuthManager:
    """
    Gestor de autenticação com sessões Flask.
    
    Suporta:
    - Autenticação por config.py (ADMIN_USERNAME, ADMIN_PASSWORD)
    - Autenticação por USERS hardcoded
    - Sessões 'user' (novo) e 'authenticated' (compatível com antigo)
    """

    @staticmethod
    def authenticate(username: str, password: str) -> bool:
        """
        Valida credenciais.
        
        Prioridade:
        1. Se config disponível → valida contra ADMIN_USERNAME/ADMIN_PASSWORD
        2. Senão → valida contra USERS
        """
        if USE_CONFIG:
            # Valida contra config
            return (username == ADMIN_USERNAME and password == ADMIN_PASSWORD)
        else:
            # Valida contra USERS (desenvolvimento)
            return USERS.get(username) == password

    @staticmethod
    def login(username: str) -> None:
        """Define utilizador na sessão (suporta modo antigo e novo)."""
        # Novo modo (session['user'])
        session['user'] = username
        
        # Modo compatível (session['authenticated'] + session['username'])
        session['authenticated'] = True
        session['username'] = username
        
        # Configura sessão como permanente
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
        - session['user'] (novo modo)
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
            'username': session.get('username'),  # Compatibilidade
            'mode': 'config' if USE_CONFIG else 'hardcoded'
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
    import sys
    print(f"✅ auth.py carregado (modo: {'config' if USE_CONFIG else 'hardcoded'})")
    if USE_CONFIG:
        print(f"   ADMIN_USERNAME: {ADMIN_USERNAME}")
    else:
        print(f"   Users disponíveis: {list(USERS.keys())}")
