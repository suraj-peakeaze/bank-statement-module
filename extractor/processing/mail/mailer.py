import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from django.template.loader import render_to_string
from datetime import datetime


class EmailService:
    def __init__(self, smtp_host="smtp.gmail.com", smtp_port=465):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = os.getenv("SMTP_EMAIL")
        self.smtp_pass = os.getenv("SMTP_PASSWORD")

    def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        attachment_path: str = None,
    ):
        """Send email with optional attachment"""
        msg = MIMEMultipart("alternative")
        msg["From"] = f"Bank Statement Processor <{self.smtp_user}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # Add HTML content
        msg.attach(MIMEText(html_content, "html"))

        # Add attachment if provided and exists
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())

            encoders.encode_base64(part)
            filename = os.path.basename(attachment_path)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename= {filename}",
            )
            msg.attach(part)

        try:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            return True
        except smtplib.SMTPException as e:
            raise Exception(f"Error sending email: {str(e)}")

    def send_processing_complete_notification(
        self,
        user_email: str,
        pdf_name: str,
        csv_path: str,
        processing_time: str = "Unknown",
        record_count: int = 0,
    ):
        """Send bank statement processing completion notification with CSV attachment"""

        context = {
            "recipient_name": user_email.split("@")[0].title(),
            "original_filename": pdf_name,
            "processing_date": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
            "processing_time": processing_time,
            "record_count": record_count,
            "csv_filename": (
                os.path.basename(csv_path)
                if csv_path
                else "processed_bank_statement.csv"
            ),
        }

        # Render email content using your template
        html_content = render_to_string(
            "mail_template.html", context
        )

        subject = f"Bank Statement Processing Complete - {pdf_name}"

        return self._send_email(
            to_email=user_email,
            subject=subject,
            html_content=html_content,
            attachment_path=csv_path,
        )
