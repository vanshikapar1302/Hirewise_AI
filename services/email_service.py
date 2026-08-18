import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, render_template
from database.connection import db
from models.email_log import EmailLog
from datetime import datetime

class EmailService:
    @staticmethod
    def _send_smtp(app, msg, user_id, email, subject, event_type, ip_address):
        """Internal helper to connect to SMTP and log outcome in app context."""
        with app.app_context():
            # Setup log entry
            log = EmailLog(
                user_id=user_id,
                email=email,
                subject=subject,
                event_type=event_type,
                status='pending',
                ip_address=ip_address
            )
            db.session.add(log)
            db.session.commit()
            
            mail_server = app.config.get("MAIL_SERVER", "").strip()
            mail_port = app.config.get("MAIL_PORT", 587)
            mail_user = app.config.get("MAIL_USERNAME", "").strip()
            mail_pass = app.config.get("MAIL_PASSWORD", "").strip()
            mail_use_tls = app.config.get("MAIL_USE_TLS", True)
            
            if not mail_server:
                print(f"[WARNING] Email not sent (SMTP server not configured): {subject} to {email}")
                log.status = 'failed: SMTP server not configured'
                db.session.commit()
                return

            try:
                # Format MIME Message
                msg['From'] = mail_user or "no-reply@hirewise.ai"
                msg['To'] = email
                msg['Subject'] = subject

                # Connect SMTP
                server = smtplib.SMTP(mail_server, mail_port, timeout=15)
                
                if mail_use_tls:
                    server.starttls()
                
                if mail_user and mail_pass:
                    server.login(mail_user, mail_pass)
                
                server.sendmail(msg['From'], [email], msg.as_string())
                server.quit()
                
                log.status = 'sent'
                log.sent_at = datetime.utcnow()
                db.session.commit()
                print(f"[SUCCESS] Asynchronously sent email: {subject} to {email}")
            except Exception as e:
                db.session.rollback()
                log.status = f"failed: {str(e)}"
                db.session.commit()
                print(f"[ERROR] Failed to send email: {e}")

    @classmethod
    def send_email_async(cls, to_email, subject, template_name, context, user_id=None, event_type="general", ip_address=None):
        """Public method to spawn a thread to send an HTML email asynchronously."""
        from flask import has_app_context
        if not has_app_context():
            print(f"[WARNING] Email '{subject}' to {to_email} skipped because not in active Flask application context.")
            return False
            
        # Grab current application object for the thread context
        app = current_app._get_current_object()
        
        # Render HTML body inside main thread request context to have access to request and session
        try:
            html_content = render_template(f"emails/{template_name}", **context)
        except Exception as e:
            print(f"[ERROR] Failed to render template '{template_name}': {e}")
            return False

        # Build multipart container
        msg = MIMEMultipart('alternative')
        part_html = MIMEText(html_content, 'html')
        msg.attach(part_html)

        # Spawn background execution thread
        thr = threading.Thread(
            target=cls._send_smtp,
            args=(app, msg, user_id, to_email, subject, event_type, ip_address)
        )
        thr.daemon = True
        thr.start()
        return True
