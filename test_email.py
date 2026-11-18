from app.services.email import send_email

send_email(
    subject="AI News Aggregator - OAuth Test",
    body_text="Your Gmail OAuth integration is working successfully!",
    body_html="""
    <h2>OAuth Test Successful</h2>
    <p>Your AI News Aggregator can now send emails through Gmail API.</p>
    """
)

print("Test email sent successfully!")