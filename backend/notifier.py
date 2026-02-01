#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
backend/notifier.py - Email Notification Manager for Rental Calendar Sync

Versão: 1.0 Final
Data: 01 de fevereiro de 2026
Desenvolvido por: PBrandão
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import smtplib

# ============================================================================
# LOGGING SETUP
# ============================================================================

logger = logging.getLogger(__name__)

# ============================================================================
# EMAIL NOTIFIER CLASS
# ============================================================================


class EmailNotifier:
    """Gerenciador de notificações por email para sincronização de calendários."""

    def __init__(self):
        """Inicializa notificador de email com configuração de .env ou config.py."""
        # ✅ ALINHADO COM CONFIG.PY
        try:
            from config import get_config

            cfg = get_config()
            self.smtp_server = cfg.EMAIL_SERVER or "smtp.gmail.com"
            self.smtp_port = cfg.EMAIL_PORT or 587
            self.email_user = cfg.EMAIL_USER
            self.email_password = cfg.EMAIL_PASSWORD
            self.notification_email = cfg.NOTIFICATION_EMAIL
            self.error_email = cfg.ERROR_EMAIL or self.notification_email
            self.enabled = cfg.EMAIL_NOTIFIER_ENABLED
            self.send_log = cfg.EMAIL_ATTACH_LOG

        except ImportError:
            # Fallback se config.py não estiver disponível (CLI directo)
            self.smtp_server = os.getenv("EMAIL_SERVER", "smtp.gmail.com")
            self.smtp_port = int(os.getenv("EMAIL_PORT", "587"))
            self.email_user = os.getenv("EMAIL_USER")
            self.email_password = os.getenv("EMAIL_PASSWORD")
            self.notification_email = os.getenv("NOTIFICATION_EMAIL")
            self.error_email = (
                os.getenv("ERROR_EMAIL") or self.notification_email
            )
            self.enabled = (
                os.getenv("EMAIL_NOTIFIER_ENABLED", "true").lower() == "true"
            )
            self.send_log = (
                os.getenv("EMAIL_ATTACH_LOG", "true").lower() == "true"
            )

    def validate_config(self) -> bool:
        """
        Valida se configuração de email está completa.

        Verifica se todos os parâmetros necessários estão configurados.

        Returns:
            True se configuração válida, False caso contrário
        """
        required = [
            ("EMAIL_SERVER", self.smtp_server),
            ("EMAIL_USER", self.email_user),
            ("EMAIL_PASSWORD", self.email_password),
            ("NOTIFICATION_EMAIL", self.notification_email),
        ]

        missing = [name for name, value in required if not value]

        if missing:
            logger.warning(
                f"❌ Email notifier not fully configured. Missing: {', '.join(missing)}"
            )
            return False

        logger.info("✅ Email notifier configuration valid")
        return True

    def _send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None,
    ) -> bool:
        """
        Envia email via SMTP.

        Args:
            to_email: Email do destinatário
            subject: Assunto do email
            body: Corpo da mensagem (texto simples)
            attachments: Lista de caminhos de ficheiros para anexar

        Returns:
            True se email enviado com sucesso, False caso contrário
        """
        if not self.enabled:
            logger.debug("📧 Email notifications are disabled")
            return False

        if not self.validate_config():
            return False

        try:
            # Criar mensagem
            msg = MIMEMultipart()
            msg["From"] = self.email_user
            msg["To"] = to_email
            msg["Subject"] = subject

            # Adicionar corpo com UTF-8 e encoding correcto
            text_part = MIMEText(body, "plain", "utf-8")
            text_part["Content-Transfer-Encoding"] = "8bit"
            msg.attach(text_part)

            # Anexar ficheiros se fornecidos
            if attachments:
                for file_path in attachments:
                    if Path(file_path).exists():
                        self._attach_file(msg, file_path)

            # Conectar e enviar via SMTP
            with smtplib.SMTP(
                self.smtp_server, self.smtp_port, timeout=10
            ) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)

            logger.info(f"✅ Email sent to {to_email}")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("❌ SMTP authentication error - check credentials")
            return False

        except smtplib.SMTPException as e:
            logger.error(f"❌ SMTP error: {e}")
            return False

        except Exception as e:
            logger.error(f"❌ Error sending email: {e}")
            return False

    def _attach_file(self, msg: MIMEMultipart, file_path: str) -> None:
        """
        Anexa ficheiro à mensagem de email.

        Args:
            msg: Objeto MIMEMultipart da mensagem
            file_path: Caminho do ficheiro a anexar
        """
        try:
            file_path = Path(file_path)

            with open(file_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)

                # RFC 5987 compliant filename format
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{file_path.name}"',
                )

                msg.attach(part)

            logger.debug(f"📎 Attached file: {file_path.name}")

        except Exception as e:
            logger.error(f"Error attaching {file_path}: {e}")

    def send_success(
        self,
        total_events: int,
        reserved_count: int,
        log_file: str = "sync.log",
    ) -> bool:
        """
        Envia email notificando sincronização bem-sucedida.

        Called by sync.py após sincronização completa sem erros.

        Args:
            total_events: Total de eventos gerados (reservas + prep times)
            reserved_count: Número de reservas processadas
            log_file: Caminho do ficheiro de log a anexar (opcional)

        Returns:
            True se email enviado com sucesso, False caso contrário

        Example:
            notifier = EmailNotifier()
            notifier.send_success(total_events=15, reserved_count=5)
        """
        current_date = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        subject = "✅ Sincronização Calendários Concluída"

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

Sistema de Sincronização
Rental Calendar Sync

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        attachments = []
        if self.send_log and Path(log_file).exists():
            attachments.append(log_file)

        return self._send_email(
            self.notification_email,
            subject,
            body,
            attachments,
        )

    def send_error(
        self, error_msg: str, log_file: str = "sync.log"
    ) -> bool:
        """
        Envia email notificando erro na sincronização com log anexado.

        Called by sync.py quando ocorre erro durante sincronização.

        Args:
            error_msg: Mensagem descrevendo o erro
            log_file: Caminho do ficheiro de log a anexar

        Returns:
            True se email enviado com sucesso, False caso contrário

        Example:
            notifier = EmailNotifier()
            notifier.send_error("Failed to download calendar", "sync.log")
        """
        current_date = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        subject = f"❌ Erro na Sincronização Calendários - {current_date}"

        # Ler últimas linhas do log para contexto
        log_content = ""
        if Path(log_file).exists():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    log_lines = f.readlines()
                    log_content = "".join(
                        log_lines[-50:]
                    )  # Últimas 50 linhas

            except Exception as e:
                log_content = f"Error reading log: {e}"

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
• Limitação de requisições das APIs

✅ AÇÕES RECOMENDADAS:

1. Verifique .env com URLs corretas
2. Verifique se URLs estão acessíveis
3. Verifique logs anexados (sync.log)
4. Execute manualmente para debug
5. Contacte suporte se persistir

📎 FICHEIRO ANEXADO:

• sync.log (log completo de sincronização)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sistema de Sincronização
Rental Calendar Sync

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        attachments = []
        if Path(log_file).exists():
            attachments.append(log_file)

        return self._send_email(
            self.error_email,
            subject,
            body,
            attachments,
        )

    def send_daily_report(self, report_data: Dict) -> bool:
        """
        Envia email com relatório diário de sincronização.

        Args:
            report_data: Dicionário com dados do relatório:
                - total_events (int): Total de eventos processados
                - success_count (int): Sincronizações bem-sucedidas
                - error_count (int): Sincronizações com erro
                - avg_sync_time (float): Tempo médio de sincronização em segundos

        Returns:
            True se email enviado com sucesso, False caso contrário

        Example:
            notifier = EmailNotifier()
            notifier.send_daily_report({
                'total_events': 50,
                'success_count': 48,
                'error_count': 2,
                'avg_sync_time': 2.5
            })
        """
        current_date = datetime.now().strftime("%d/%m/%Y")
        current_timestamp = datetime.utcnow().isoformat() + "Z"

        subject = f"📊 Relatório Sincronização - {current_date}"

        body = f"""Relatório diário de sincronização

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 RELATÓRIO DIÁRIO - {current_date}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 ESTATÍSTICAS:

• Total de eventos: {report_data.get('total_events', 0)}
• Sincronizações bem-sucedidas: {report_data.get('success_count', 0)}
• Sincronizações com erro: {report_data.get('error_count', 0)}
• Tempo médio: {report_data.get('avg_sync_time', 0):.2f}s

⏱️ DATA: {current_date}

🕐 TIMESTAMP: {current_timestamp}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sistema de Sincronização
Rental Calendar Sync

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        return self._send_email(
            self.notification_email,
            subject,
            body,
        )


# ============================================================================
# TEST - Email Configuration Validation
# ============================================================================


def test_email_config() -> None:
    """Testa e exibe configuração de email."""
    logger.info("=" * 70)
    logger.info("📧 EMAIL CONFIGURATION TEST")
    logger.info("=" * 70)
    logger.info("")

    notifier = EmailNotifier()

    logger.info(f"Status: {'✅ ENABLED' if notifier.enabled else '❌ DISABLED'}")
    logger.info(f"SMTP Server: {notifier.smtp_server}")
    logger.info(f"SMTP Port: {notifier.smtp_port}")
    logger.info(
        f"Email User: {'*' * len(notifier.email_user) if notifier.email_user else '⚠️ NOT CONFIGURED'}"
    )
    logger.info(
        f"Notification Email: {notifier.notification_email or '⚠️ NOT CONFIGURED'}"
    )
    logger.info(f"Attach Log: {'✅ YES' if notifier.send_log else '❌ NO'}")

    logger.info("=" * 70)
    logger.info("")

    if notifier.validate_config():
        logger.info("✅ Email configuration is valid and ready to use")
    else:
        logger.warning("⚠️ Email configuration is incomplete")

    logger.info("")
    logger.info("=" * 70)


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
    )
    test_email_config()
