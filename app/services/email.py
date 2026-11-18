
import os
import base64
import logging
import html
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
import markdown

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

logger = logging.getLogger(__name__)

MY_EMAIL = os.getenv("MY_EMAIL")

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CREDENTIALS_FILE = Path(
    os.getenv(
        "GOOGLE_OAUTH_CREDENTIALS_PATH",
        str(PROJECT_ROOT / "credentials.json")
    )
).expanduser()

TOKEN_FILE = Path(
    os.getenv(
        "GOOGLE_OAUTH_TOKEN_PATH",
        str(PROJECT_ROOT / "token.json")
    )
).expanduser()


def _get_gmail_service():
    """Authenticate using Gmail OAuth 2.0 and return Gmail API service."""

    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"OAuth credentials file not found: {CREDENTIALS_FILE}"
        )

    creds = None

    # Load previously saved OAuth credentials.
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(TOKEN_FILE),
                SCOPES
            )
        except (ValueError, OSError) as exc:
            logger.warning(
                "Unable to load OAuth token. Reauthorization required: %s",
                exc
            )

    # Refresh expired access token.
    if creds and creds.expired and creds.refresh_token:
        try:
            logger.info("Refreshing Gmail OAuth access token...")
            creds.refresh(Request())

        except RefreshError as exc:
            logger.warning(
                "OAuth refresh failed. Starting authorization again: %s",
                exc
            )
            creds = None

    # First-time authorization or expired/invalid token.
    if not creds or not creds.valid:

        logger.info("Starting Gmail OAuth authorization...")

        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE),
            SCOPES
        )

        creds = flow.run_local_server(
            port=0,
            access_type="offline",
            prompt="consent"
        )

    # Persist refreshed credentials.
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

    TOKEN_FILE.write_text(
        creds.to_json(),
        encoding="utf-8"
    )

    logger.info("Gmail OAuth authentication successful.")

    return build(
        "gmail",
        "v1",
        credentials=creds,
        cache_discovery=False
    )


def send_email(
    subject: str,
    body_text: str,
    body_html: str = None,
    recipients: list = None
):
    """Send plain-text and HTML email using Gmail API."""

    if not MY_EMAIL:
        raise ValueError(
            "MY_EMAIL environment variable is not set"
        )

    if recipients is None:
        recipients = [MY_EMAIL]

    recipients = [
        recipient.strip()
        for recipient in recipients
        if recipient and recipient.strip()
    ]

    if not recipients:
        raise ValueError("No valid recipients provided")

    # Build multipart email.
    msg = MIMEMultipart("alternative")

    msg["Subject"] = subject
    msg["From"] = MY_EMAIL
    msg["To"] = ", ".join(recipients)

    msg.attach(
        MIMEText(body_text, "plain", "utf-8")
    )

    if body_html:
        msg.attach(
            MIMEText(body_html, "html", "utf-8")
        )

    # Gmail API requires base64url-encoded MIME content.
    raw_message = base64.urlsafe_b64encode(
        msg.as_bytes()
    ).decode("utf-8")

    try:
        logger.info(
            "Sending email to %s recipient(s)...",
            len(recipients)
        )

        service = _get_gmail_service()

        result = (
            service.users()
            .messages()
            .send(
                userId="me",
                body={"raw": raw_message}
            )
            .execute()
        )

        logger.info(
            "Email sent successfully. Message ID: %s",
            result.get("id")
        )

        return result

    except HttpError as exc:
        logger.exception("Gmail API email delivery failed")

        raise RuntimeError(
            f"Gmail API email delivery failed: {exc}"
        ) from exc


def markdown_to_html(markdown_text: str) -> str:
    html = markdown.markdown(markdown_text, extensions=['extra', 'nl2br'])
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #ffffff;
        }}
        h2 {{
            font-size: 18px;
            font-weight: 600;
            color: #1a1a1a;
            margin-top: 24px;
            margin-bottom: 8px;
            line-height: 1.4;
        }}
        h3 {{
            font-size: 16px;
            font-weight: 600;
            color: #1a1a1a;
            margin-top: 20px;
            margin-bottom: 8px;
            line-height: 1.4;
        }}
        p {{
            margin: 8px 0;
            color: #4a4a4a;
        }}
        strong {{
            font-weight: 600;
            color: #1a1a1a;
        }}
        em {{
            font-style: italic;
            color: #666;
        }}
        a {{
            color: #0066cc;
            text-decoration: none;
            font-weight: 500;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        hr {{
            border: none;
            border-top: 1px solid #e5e5e5;
            margin: 20px 0;
        }}
        .greeting {{
            font-size: 16px;
            font-weight: 500;
            color: #1a1a1a;
            margin-bottom: 12px;
        }}
        .introduction {{
            color: #4a4a4a;
            margin-bottom: 20px;
        }}
        .article-link {{
            display: inline-block;
            margin-top: 8px;
            color: #0066cc;
            font-size: 14px;
        }}
    </style>
</head>
<body>
{html}
</body>
</html>"""


def digest_to_html(digest_response) -> str:
    from app.agent.email_agent import EmailDigestResponse
    
    if not isinstance(digest_response, EmailDigestResponse):
        return markdown_to_html(digest_response.to_markdown() if hasattr(digest_response, 'to_markdown') else str(digest_response))
    
    html_parts = []
    greeting_html = markdown.markdown(digest_response.introduction.greeting, extensions=['extra', 'nl2br'])
    introduction_html = markdown.markdown(digest_response.introduction.introduction, extensions=['extra', 'nl2br'])
    html_parts.append(f'<div class="greeting">{greeting_html}</div>')
    html_parts.append(f'<div class="introduction">{introduction_html}</div>')
    html_parts.append('<hr>')
    
    for article in digest_response.articles:
        html_parts.append(f'<h3>{html.escape(article.title)}</h3>')
        summary_html = markdown.markdown(article.summary, extensions=['extra', 'nl2br'])
        html_parts.append(f'<div>{summary_html}</div>')
        html_parts.append(f'<p><a href="{html.escape(article.url)}" class="article-link">Read more →</a></p>')
        html_parts.append('<hr>')
    
    html_content = '\n'.join(html_parts)
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #ffffff;
        }}
        h3 {{
            font-size: 16px;
            font-weight: 600;
            color: #1a1a1a;
            margin-top: 20px;
            margin-bottom: 8px;
            line-height: 1.4;
        }}
        p {{
            margin: 8px 0;
            color: #4a4a4a;
        }}
        strong {{
            font-weight: 600;
            color: #1a1a1a;
        }}
        em {{
            font-style: italic;
            color: #666;
        }}
        a {{
            color: #0066cc;
            text-decoration: none;
            font-weight: 500;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        hr {{
            border: none;
            border-top: 1px solid #e5e5e5;
            margin: 20px 0;
        }}
        .greeting {{
            font-size: 16px;
            font-weight: 500;
            color: #1a1a1a;
            margin-bottom: 12px;
        }}
        .introduction {{
            color: #4a4a4a;
            margin-bottom: 20px;
        }}
        .article-link {{
            display: inline-block;
            margin-top: 8px;
            color: #0066cc;
            font-size: 14px;
        }}
        .greeting p {{
            margin: 0;
        }}
        .introduction p {{
            margin: 0;
        }}
        div {{
            margin: 8px 0;
            color: #4a4a4a;
        }}
        div p {{
            margin: 4px 0;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""


def send_email_to_self(subject: str, body: str):
    if not MY_EMAIL:
        raise ValueError("MY_EMAIL environment variable is not set. Please set it in your .env file.")
    send_email(subject, body, recipients=[MY_EMAIL])


if __name__ == "__main__":
    send_email_to_self("Test from Python", "Hello from my script.")