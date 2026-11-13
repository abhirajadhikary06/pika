"""Notification-related Celery tasks."""
import smtplib
from email.message import EmailMessage
from flask import current_app
from app import celery, db
from app.models.ticket import Ticket, Comment
from app.models.workspace import Invitation
from app.models.user import User
import structlog

logger = structlog.get_logger()


def _send_email(to: str, subject: str, body: str) -> None:
    host = current_app.config.get("SMTP_HOST")
    sender = current_app.config.get("SMTP_FROM")
    username = current_app.config.get("SMTP_USERNAME")
    password = current_app.config.get("SMTP_PASSWORD")
    if not host or not sender:
        raise RuntimeError("SMTP_HOST and SMTP_FROM must be configured to send email.")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(host, current_app.config["SMTP_PORT"], timeout=30) as server:
        if current_app.config.get("SMTP_USE_TLS", True):
            server.starttls()
        if username and password:
            server.login(username, password)
        server.send_message(message)


@celery.task(bind=True, max_retries=3, default_retry_delay=60, name="tasks.send_invitation_email")
def send_invitation_email(self, invitation_id: str):
    """Send a workspace invitation email through the configured SMTP server."""
    try:
        inv = Invitation.query.get(invitation_id)
        if not inv or inv.status != "pending":
            logger.info("invitation_email_skipped", invitation_id=invitation_id)
            return {"status": "skipped"}

        invite_url = f"{current_app.config['FRONTEND_URL']}/invite/{inv.token}"
        _send_email(
            inv.email,
            f"Invitation to join {inv.workspace.name} on Pika",
            (
                f"You have been invited to join {inv.workspace.name} on Pika.\n\n"
                f"Accept the invitation: {invite_url}\n\n"
                "This invitation expires in 7 days."
            ),
        )
        logger.info("invitation_email_sent", invitation_id=invitation_id, email=inv.email)
        return {"status": "sent", "email": inv.email}
    except Exception as exc:
        logger.exception("invitation_email_failed", invitation_id=invitation_id)
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=30, name="tasks.send_ticket_assigned_notification")
def send_ticket_assigned_notification(self, ticket_id: str, assignee_id: str):
    """Notify assignee about ticket assignment (email/push stub)."""
    try:
        ticket = Ticket.query.get(ticket_id)
        user = User.query.get(assignee_id)
        if not ticket or not user:
            return {"status": "skipped"}

        _send_email(
            user.email,
            f"Ticket #{ticket.number} assigned to you",
            f"{ticket.title}\n\nOpen Pika to review this ticket.",
        )
        logger.info("assignment_notification_sent", ticket_id=ticket_id, assignee_email=user.email)
        return {"status": "sent"}
    except Exception as exc:
        logger.exception("assignment_notification_failed", ticket_id=ticket_id)
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=30, name="tasks.send_ticket_reply_notification")
def send_ticket_reply_notification(self, ticket_id: str, comment_id: str):
    """Notify relevant parties about a new reply."""
    try:
        ticket = Ticket.query.get(ticket_id)
        comment = Comment.query.get(comment_id)
        if not ticket or not comment:
            return {"status": "skipped"}

        recipients = {u.email for u in (ticket.created_by, ticket.assignee) if u and not comment.is_internal}
        for recipient in recipients:
            _send_email(
                recipient,
                f"New reply on ticket #{ticket.number}",
                f"{ticket.title}\n\n{comment.body}",
            )
        logger.info("reply_notification_sent", ticket_id=ticket_id, comment_id=comment_id)
        return {"status": "sent"}
    except Exception as exc:
        logger.exception("reply_notification_failed", ticket_id=ticket_id)
        raise self.retry(exc=exc)
