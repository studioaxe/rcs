#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""
EMAIL HANDLER - Notificações de Sincronização

Responsabilidades:
├─ Enviar emails de sucesso
├─ Enviar emails de erro com log anexado
├─ Registar tentativas
└─ Tratamento de exceções

Uso:
├─ from email_handler import EmailNotifier
├─ notifier = EmailNotifier()
├─ notifier.send_success(total_events, reserved_count)
└─ notifier.send_error(error_msg, log_file)

Versão: 1.1
Data: 19 de Dezembro de 2025
"""

import os
import sys
import smtplib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# ==================== CONFIGURAÇÃO ====================

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Gerenciador de notificações por email"""

    def __init__(self):
        """Inicializa notificador de email"""
        self.smtp_server = os.getenv('EMAIL_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('EMAIL_PORT', 587))
        self.email_user = os.getenv('EMAIL_USER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.notification_email = os.getenv('NOTIFICATION_EMAIL')
        self.error_email = os.getenv('ERROR_EMAIL', self.notification_email)
        self.enabled = os.getenv('EMAIL_ON_ERROR', 'true').lower() == 'true'
        self.send_log = os.getenv('EMAIL_ATTACH_LOG', 'true').lower() == 'true'

    def validate_config(self) -> bool:
        """Valida se configuração de email está completa"""
        required = [
            ('EMAIL_SERVER', self.smtp_server),
            ('EMAIL_USER', self.email_user),
            ('EMAIL_PASSWORD', self.email_password),
            ('NOTIFICATION_EMAIL', self.notification_email),
        ]

        missing = [name for name, value in required if not value]

        if missing:
            logger.error(f"Email não configurado. Faltam: {', '.join(missing)}")
            return False

        return True

    def _send_email(self, to_email: str, subject: str, body: str,
                    attachments: list = None) -> bool:
        """
        Envia email via SMTP

        Args:
            to_email: Email destinatário
            subject: Assunto
            body: Corpo da mensagem
            attachments: Lista de caminhos de ficheiros para anexar

        Returns:
            True se sucesso, False se erro
        """
        if not self.enabled:
            logger.debug("Email desativado")
            return False

        if not self.validate_config():
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # Anexar ficheiros
            if attachments:
                for file_path in attachments:
                    if Path(file_path).exists():
                        self._attach_file(msg, file_path)

            # Conectar e enviar
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)

            logger.info(f"✅ Email enviado para {to_email}")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("❌ Erro de autenticação SMTP")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"❌ Erro SMTP: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao enviar email: {e}")
            return False

    def _attach_file(self, msg: MIMEMultipart, file_path: str) -> None:
        """Anexa ficheiro a mensagem"""
        try:
            file_path = Path(file_path)
            with open(file_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {file_path.name}'
                )
                msg.attach(part)
            logger.debug(f"Ficheiro anexado: {file_path.name}")
        except Exception as e:
            logger.error(f"Erro ao anexar {file_path}: {e}")

    def send_success(self, total_events: int, reserved_count: int,
                     log_file: str = 'sync.log') -> bool:
        """
        Envia email de sucesso

        Args:
            total_events: Total de eventos gerados
            reserved_count: Número de reservas processadas
            log_file: Caminho do ficheiro de log

        Returns:
            True se sucesso
        """
        current_date = datetime.now().strftime('%d/%m/%Y às %H:%M:%S')
        current_timestamp = datetime.utcnow().isoformat() + 'Z'

        subject = '✅ Sincronização Calendários Completa'

        body = f"""Sincronização de calendários concluída com sucesso!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ STATUS: SUCESSO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 ESTATÍSTICAS:
• Total de eventos: {total_events}
• Reservas processadas: {reserved_count}
• Eventos por reserva: 3 (Reserva + TP Antes + TP Depois)

📅 PLATAFORMAS:
✅ Airbnb: OK
✅ Booking: OK
✅ Vrbo: OK

⏱️ DATA/HORA: {current_date}
🕐 TIMESTAMP: {current_timestamp}

📁 FICHEIRO: master_calendar.ics
└─ Agora disponível no repositório (branch main)

🚀 PRÓXIMOS PASSOS:
1. Verifique o repositório
2. Sincronize em Airbnb
3. Sincronize em Booking
4. Sincronize em Vrbo

📋 DETALHES NO LOG ANEXADO

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sistema de Sincronização v2.3
Rental Calendar Master
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        attachments = []
        if self.send_log and Path(log_file).exists():
            attachments.append(log_file)

        return self._send_email(
            self.notification_email,
            subject,
            body,
            attachments
        )

    def send_error(self, error_msg: str, log_file: str = 'sync.log') -> bool:
        """
        Envia email de erro com log anexado

        Args:
            error_msg: Mensagem de erro
            log_file: Caminho do ficheiro de log

        Returns:
            True se sucesso
        """
        current_date = datetime.now().strftime('%d/%m/%Y às %H:%M:%S')
        current_timestamp = datetime.utcnow().isoformat() + 'Z'

        subject = f'❌ Erro na Sincronização Calendários - {current_date}'

        # Ler log para contexto
        log_content = ""
        if Path(log_file).exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_lines = f.readlines()
                    log_content = ''.join(log_lines[-50:])  # Últimas 50 linhas
            except Exception as e:
                log_content = f"Erro ao ler log: {e}"

        body = f"""ERRO detectado na sincronização de calendários!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ STATUS: ERRO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ ERRO:
{error_msg}

⏱️ DATA/HORA: {current_date}
🕐 TIMESTAMP: {current_timestamp}

📋 LOG (últimas 50 linhas):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{log_content}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 POSSÍVEIS CAUSAS:
• URLs iCal inválidas ou expiradas
• Problema de conexão de rede
• Erro nos dados do calendário
• Configuração de ambiente incorreta

✅ AÇÕES RECOMENDADAS:
1. Verifique .env com URLs corretas
2. Verifique se URLs estão acessíveis
3. Verifique logs anexados (sync.log)
4. Execute manualmente para debug
5. Contacte suporte se persistir

📎 FICHEIROS ANEXADOS:
• sync.log (completo)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sistema de Sincronização v2.3
Rental Calendar Master
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        attachments = []
        if Path(log_file).exists():
            attachments.append(log_file)

        return self._send_email(
            self.error_email,
            subject,
            body,
            attachments
        )

    def send_daily_report(self, report_data: dict) -> bool:
        """
        Envia relatório diário

        Args:
            report_data: Dicionário com dados do relatório
                {
                    'total_events': int,
                    'success_count': int,
                    'error_count': int,
                    'avg_sync_time': float,
                }
        """
        current_date = datetime.now().strftime('%d/%m/%Y')
        current_timestamp = datetime.utcnow().isoformat() + 'Z'

        subject = f'📊 Relatório Sincronização - {current_date}'

        body = f"""Relatório diário de sincronização

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 RELATÓRIO DIÁRIO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 ESTATÍSTICAS:
• Total de eventos: {report_data.get('total_events', 0)}
• Sincronizações bem-sucedidas: {report_data.get('success_count', 0)}
• Sincronizações com erro: {report_data.get('error_count', 0)}
• Tempo médio: {report_data.get('avg_sync_time', 0):.2f}s

⏱️ DATA: {current_date}
🕐 TIMESTAMP: {current_timestamp}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sistema de Sincronização v2.3
Rental Calendar Master
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        return self._send_email(
            self.notification_email,
            subject,
            body
        )


# ==================== TESTE ====================

def test_email_config():
    """Testa configuração de email"""
    notifier = EmailNotifier()

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("📧 TESTE DE CONFIGURAÇÃO EMAIL")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    print(f"Email Ativado: {notifier.enabled}")
    print(f"SMTP Server: {notifier.smtp_server}")
    print(f"SMTP Port: {notifier.smtp_port}")
    print(f"Email User: {'*' * len(notifier.email_user) if notifier.email_user else 'Não configurado'}")
    print(f"Notification Email: {notifier.notification_email}")
    print(f"Send Log Attachment: {notifier.send_log}")
    print()

    if notifier.validate_config():
        print("✅ Configuração válida!")
    else:
        print("❌ Configuração incompleta!")

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


if __name__ == "__main__":
    test_email_config()
