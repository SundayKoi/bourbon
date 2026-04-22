"""Email notifier for daily/weekly digest delivery."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from src.config import EmailConfig
from src.models import Listing
from src.notifiers.base import AbstractNotifier

logger = structlog.get_logger()


class EmailNotifier(AbstractNotifier):
    def __init__(self, config: EmailConfig) -> None:
        self.config = config

    def notify(self, listing: Listing) -> None:
        """Not used for email — use send_digest instead."""
        pass

    def notify_admin(self, message: str) -> None:
        """Send admin alert via email."""
        if not self.config.enabled:
            return
        self._send_email(
            subject="⚠️ Bourbon Alerts Admin",
            body=message,
        )

    def send_digest(self, listings: list[dict]) -> None:
        """Send a digest email with all recent non-watchlist listings."""
        if not self.config.enabled or not listings:
            return

        html = self._build_digest_html(listings)
        self._send_email(
            subject=f"🥃 Bourbon Digest — {len(listings)} new listings",
            body=html,
            html=True,
        )

    def _build_digest_html(self, listings: list[dict]) -> str:
        rows = ""
        for item in listings:
            price = f"${item['price']:,.2f}" if item.get("price") else "N/A"
            rows += f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #eee">
                    <a href="{item['url']}">{item['title']}</a>
                </td>
                <td style="padding:8px;border-bottom:1px solid #eee">{price}</td>
                <td style="padding:8px;border-bottom:1px solid #eee">{item['source']}</td>
            </tr>"""

        return f"""
        <html>
        <body style="font-family:sans-serif;max-width:600px;margin:auto">
            <h2>🥃 Your Bourbon Digest</h2>
            <p>{len(listings)} new listings found:</p>
            <table style="width:100%;border-collapse:collapse">
                <tr style="background:#f5f5f5">
                    <th style="padding:8px;text-align:left">Listing</th>
                    <th style="padding:8px;text-align:left">Price</th>
                    <th style="padding:8px;text-align:left">Source</th>
                </tr>
                {rows}
            </table>
        </body>
        </html>"""

    def _send_email(self, subject: str, body: str, html: bool = False) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.from_addr
        msg["To"] = self.config.to_addr

        content_type = "html" if html else "plain"
        msg.attach(MIMEText(body, content_type))

        try:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_pass)
                server.send_message(msg)
            logger.info("email.sent", subject=subject)
        except Exception as e:
            logger.error("email.send_error", error=str(e))
            raise
