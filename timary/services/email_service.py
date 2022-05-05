from django.core.mail import send_mail


class EmailService:
    @staticmethod
    def send_email(subject, body=None, recipients=None, is_html=False):
        send_mail(
            subject,
            body if not is_html else None,
            None,
            recipient_list=recipients if isinstance(recipients, list) else [recipients],
            fail_silently=False,
            html_message=body if is_html else None,
        )

    @staticmethod
    def send_plain(subject, body, recipients):
        EmailService.send_email(subject, body, recipients, is_html=False)

    @staticmethod
    def send_html(
        subject,
        html,
        recipients,
    ):
        EmailService.send_email(subject, html, recipients, is_html=True)
