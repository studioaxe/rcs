#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TEST RUNNER - Validação de Configuração Full Auto

Verifica:
├─ Dependências Python
├─ Variáveis de ambiente
├─ Configuração Email SMTP
├─ URLs iCal acessíveis
└─ Permissões de ficheiros

Uso:
    python test_full_auto_setup.py
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# Cores para output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(title):
    """Imprime cabeçalho"""
    print(f"\n{BLUE}{BOLD}{'='*60}{RESET}")
    print(f"{BLUE}{BOLD}{title:^60}{RESET}")
    print(f"{BLUE}{BOLD}{'='*60}{RESET}\n")

def print_section(title):
    """Imprime secção"""
    print(f"\n{BOLD}📋 {title}{RESET}")
    print("-" * 60)

def print_check(text, status):
    """Imprime check"""
    symbol = f"{GREEN}✅{RESET}" if status else f"{RED}❌{RESET}"
    print(f"{symbol} {text}")

def print_warning(text):
    """Imprime aviso"""
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_error(text):
    """Imprime erro"""
    print(f"{RED}❌ {text}{RESET}")

def print_success(text):
    """Imprime sucesso"""
    print(f"{GREEN}✅ {text}{RESET}")

# ==================== TESTES ====================

def test_python_dependencies():
    """Testa dependências Python"""
    print_section("Dependências Python")
    
    dependencies = {
        'icalendar': 'icalendar',
        'requests': 'requests',
        'dotenv': 'dotenv',
        'pytz': 'pytz',
        'email': 'email (built-in)',
        'smtplib': 'smtplib (built-in)',
    }
    
    missing = []
    
    for name, package in dependencies.items():
        try:
            __import__(name)
            print_check(f"Importar: {package}", True)
        except ImportError:
            print_check(f"Importar: {package}", False)
            missing.append(package)
    
    if missing:
        print_error(f"\nFaltam dependências: {', '.join(missing)}")
        print(f"  Instalar: pip install {' '.join(m.split()[0] for m in missing if '(' not in m)}")
        return False
    
    print_success("Todas as dependências OK!")
    return True

def test_environment_variables():
    """Testa variáveis de ambiente"""
    print_section("Variáveis de Ambiente")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    required = {
        'AIRBNB_ICAL_URL': 'URL do Airbnb',
        'BOOKING_ICAL_URL': 'URL do Booking',
        'VRBO_ICAL_URL': 'URL do Vrbo',
        'EMAIL_SERVER': 'Servidor SMTP',
        'EMAIL_PORT': 'Porta SMTP',
        'EMAIL_USER': 'Email para SMTP',
        'EMAIL_PASSWORD': 'Password para SMTP',
        'NOTIFICATION_EMAIL': 'Email de notificações',
    }
    
    optional = {
        'ERROR_EMAIL': 'Email para erros',
        'BUFFER_DAYS_BEFORE': 'Dias antes (padrão: 1)',
        'BUFFER_DAYS_AFTER': 'Dias depois (padrão: 1)',
    }
    
    missing = []
    
    print(f"{BOLD}Obrigatórias:{RESET}")
    for var, desc in required.items():
        value = os.getenv(var)
        if value:
            masked = value[:20] + '...' if len(value) > 20 else value
            print_check(f"{var}: {desc}", True)
        else:
            print_check(f"{var}: {desc}", False)
            missing.append(var)
    
    print(f"\n{BOLD}Opcionais:{RESET}")
    for var, desc in optional.items():
        value = os.getenv(var)
        if value:
            print_check(f"{var}: {desc} = {value}", True)
        else:
            print_warning(f"{var}: {desc} (não definido, usando padrão)")
    
    if missing:
        print_error(f"\nFaltam variáveis: {', '.join(missing)}")
        print(f"\n  1. Copiar .env.example → .env")
        print(f"  2. Editar .env com valores reais")
        print(f"  3. Executar novamente")
        return False
    
    print_success("Todas as variáveis OK!")
    return True

def test_email_config():
    """Testa configuração de email"""
    print_section("Configuração Email SMTP")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    import smtplib
    
    smtp_server = os.getenv('EMAIL_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('EMAIL_PORT', 587))
    email_user = os.getenv('EMAIL_USER')
    email_password = os.getenv('EMAIL_PASSWORD')
    
    print(f"Servidor: {smtp_server}:{smtp_port}")
    print(f"Utilizador: {email_user}")
    print()
    
    try:
        print("🔌 Conectando ao servidor SMTP...")
        with smtplib.SMTP(smtp_server, smtp_port, timeout=5) as server:
            server.starttls()
            print_check("Conexão SMTP", True)
            
            print("🔐 Autenticando...")
            server.login(email_user, email_password)
            print_check("Autenticação", True)
        
        print_success("Email SMTP configurado corretamente!")
        return True
    
    except smtplib.SMTPAuthenticationError:
        print_error("Erro de autenticação! Verificar email e password")
        return False
    except smtplib.SMTPException as e:
        print_error(f"Erro SMTP: {e}")
        return False
    except Exception as e:
        print_error(f"Erro ao conectar: {e}")
        return False

def test_ical_urls():
    """Testa URLs iCal"""
    print_section("URLs iCal")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    import requests
    
    urls = {
        'AIRBNB': os.getenv('AIRBNB_ICAL_URL'),
        'BOOKING': os.getenv('BOOKING_ICAL_URL'),
        'VRBO': os.getenv('VRBO_ICAL_URL'),
    }
    
    for name, url in urls.items():
        if not url:
            print_check(f"{name}: URL não configurada", False)
            continue
        
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                size = len(response.content)
                print_check(f"{name}: {response.status_code} OK ({size} bytes)", True)
            else:
                print_check(f"{name}: {response.status_code}", False)
        except Exception as e:
            print_error(f"{name}: {str(e)}")
    
    return True

def test_file_permissions():
    """Testa permissões de ficheiros"""
    print_section("Permissões de Ficheiros")
    
    files_to_check = [
        ('sync_calendars_core_v2_3_FINAL.py', 'Leitura'),
        ('email_handler.py', 'Leitura'),
        ('.env', 'Leitura'),
    ]
    
    current_dir = Path.cwd()
    
    for filename, action in files_to_check:
        filepath = current_dir / filename
        
        if filepath.exists():
            if action == 'Leitura':
                can_read = os.access(filepath, os.R_OK)
                print_check(f"{filename}: {action}", can_read)
            else:
                can_write = os.access(filepath, os.W_OK)
                print_check(f"{filename}: {action}", can_write)
        else:
            print_warning(f"{filename}: Não encontrado (OK se em GitHub)")
    
    # Verificar se pode escrever na directoria
    can_write = os.access(current_dir, os.W_OK)
    print_check(f"Directoria atual: Escrita", can_write)
    
    return True

def test_github_files():
    """Testa ficheiros GitHub"""
    print_section("Ficheiros GitHub")
    
    github_dir = Path.cwd() / '.github' / 'workflows'
    workflow_file = github_dir / 'full_auto_workflow.yml'
    
    if github_dir.exists():
        print_check(".github/workflows/ directoria", True)
    else:
        print_warning(".github/workflows/ não existe (será criada no push)")
    
    if workflow_file.exists():
        print_check("full_auto_workflow.yml", True)
    else:
        print_warning("full_auto_workflow.yml não existe localmente")
    
    return True

# ==================== RESUMO ====================

def main():
    """Executa todos os testes"""
    
    print_header("🧪 TEST RUNNER - Full Auto Setup")
    
    tests = [
        ("Dependências Python", test_python_dependencies),
        ("Variáveis de Ambiente", test_environment_variables),
        ("Configuração Email", test_email_config),
        ("URLs iCal", test_ical_urls),
        ("Permissões de Ficheiros", test_file_permissions),
        ("Ficheiros GitHub", test_github_files),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Erro ao executar {test_name}: {e}")
            results.append((test_name, False))
    
    # ==================== RESUMO ====================
    
    print_section("📊 Resumo dos Testes")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        symbol = f"{GREEN}✅{RESET}" if result else f"{RED}❌{RESET}"
        print(f"{symbol} {test_name}")
    
    print()
    print(f"Resultado: {passed}/{total} testes passaram")
    
    if passed == total:
        print()
        print_success("🎉 Tudo OK! Full Auto pronto para usar!")
        print()
        print("Próximos passos:")
        print("1. git add .github/ email_handler.py .env.example")
        print("2. git commit -m '🚀 FASE 2: Full Auto com GitHub Actions'")
        print("3. git push origin main")
        print("4. GitHub → Actions → Run workflow")
        print()
        return 0
    else:
        print()
        print_error("❌ Alguns testes falharam. Verificar acima.")
        print()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
