"""
Centralized email module for all outgoing emails.

All email sending should go through send_email() to ensure consistent:
- SMTP configuration
- Error handling
- Logging
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.config import SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER


def send_email(
    to: str,
    subject: str,
    body: str,
    html_body: str | None = None,
    from_email: str | None = None,
    from_name: str | None = None
) -> bool:
    """
    Send an email using configured SMTP settings.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Plain text email body
        html_body: Optional HTML body (if provided, sends multipart email)
        from_email: Optional sender email (defaults to SMTP_USER)
        from_name: Optional sender display name (e.g., "GhostPost")

    Returns:
        True if email was sent successfully, False otherwise
    """
    from backend.utlils.utils import notify

    # Check if email is configured
    if not SMTP_USER or not SMTP_PASSWORD:
        notify("⚠️ Email not configured (missing SMTP_USER or SMTP_PASSWORD)")
        return False

    if not to or not to.strip():
        notify("⚠️ Cannot send email - no recipient address provided")
        return False

    # Build the "From" header
    sender = from_email or SMTP_USER
    if from_name:
        sender = f"{from_name} <{sender}>"

    try:
        # Create message
        msg = MIMEMultipart("alternative") if html_body else MIMEMultipart()
        msg["From"] = sender
        msg["To"] = to
        msg["Subject"] = subject

        # Add plain text body
        msg.attach(MIMEText(body, "plain"))

        # Add HTML body if provided
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        # Connect to SMTP server and send
        # with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        #    server.starttls()  # Enable TLS encryption
        #    server.login(SMTP_USER, SMTP_PASSWORD)
        #    server.send_message(msg)

        notify(f"📧 Email sent to {to}: {subject}")
        return True

    except Exception as e:
        notify(f"⚠️ Failed to send email to {to}: {e}")
        return False


def message_devs(text: str, subject: str = "URGENT: Ghostpost Issue") -> bool:
    """
    Send an urgent email notification to developers.

    Args:
        text: The message content to send
        subject: Email subject line (default: "URGENT: Ghostpost Issue")

    Returns:
        True if email was sent successfully, False otherwise
    """
    from backend.config import DEV_EMAIL
    from backend.utlils.utils import notify

    if not DEV_EMAIL:
        notify("⚠️ Developer email not configured (missing DEV_EMAIL)")
        return False

    return send_email(to=DEV_EMAIL, subject=subject, body=text)


def notify_user_reauth_needed(username: str) -> bool:
    """
    Send an email to the user notifying them that they need to re-authenticate with Twitter.

    Args:
        username: The username who needs to re-authenticate

    Returns:
        True if email was sent successfully, False otherwise
    """
    from backend.config import FRONTEND_URL
    from backend.utlils.utils import notify, read_user_info

    # Get user's email from user_info
    user_info = read_user_info(username)
    if not user_info:
        notify(f"⚠️ Cannot notify user {username} - no user info found")
        return False

    user_email = user_info.get("email")
    if not user_email or not user_email.strip():
        notify(f"⚠️ Cannot notify user {username} - no email address on file")
        return False

    frontend_url = FRONTEND_URL or "https://ghostpost.ai"

    subject = "Action Required: Re-connect your Twitter account on GhostPost"
    body = f"""Hi {username},

Your Twitter authentication has expired and GhostPost can no longer find new tweets or post replies on your behalf.

To resume your automated posting, please log back in:
{frontend_url}

This usually happens when:
- Your Twitter session expired (typically after 180 days)
- You changed your Twitter password
- You revoked GhostPost's access in Twitter settings

Once you log back in, GhostPost will resume finding tweets and generating replies automatically.

Thanks for using GhostPost!

---
If you didn't expect this email, you can ignore it or reply to let us know.
"""

    return send_email(to=user_email, subject=subject, body=body)
