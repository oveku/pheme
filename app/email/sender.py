"""SMTP email sender for digest delivery."""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.models import Digest
from app.email.composer import compose_digest_html, compose_digest_plain

logger = logging.getLogger(__name__)


async def send_digest_email(
    digest: Digest,
    recipient: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
) -> bool:
    """Send a digest email via SMTP.

    Returns True on success, False on failure or missing recipient.
    """
    if not recipient:
        logger.warning("No recipient configured, skipping email")
        return False

    date_str = digest.generated_at.strftime("%Y-%m-%d")
    subject = f"Pheme Daily Digest - {date_str}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = recipient

    plain_body = compose_digest_plain(digest)
    html_body = compose_digest_html(digest)

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_password,
            start_tls=True,
        )
        logger.info("Digest email sent to %s", recipient)
        return True
    except Exception as exc:
        logger.error("Failed to send digest email: %s", exc)
        return False
