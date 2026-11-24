"""
Manda cada erro 500 a quem é superusuário e equipe ao mesmo tempo, lido do cadastro.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.utils.log import AdminEmailHandler


class SuperuserEmailHandler(AdminEmailHandler):
    def send_mail(self, subject, message, *args, html_message=None, **kwargs):
        # O model só é buscado aqui: o LOGGING é montado antes de os apps carregarem.
        recipients = list(
            get_user_model().objects
            .filter(is_superuser=True, is_staff=True, is_active=True, email__isnull=False)
            .exclude(email='')
            .values_list('email', flat=True)
        )
        if not recipients:
            return
        mail = EmailMultiAlternatives(
            subject=settings.EMAIL_SUBJECT_PREFIX + subject,
            body=message,
            from_email=settings.SERVER_EMAIL,
            to=recipients,
        )
        if html_message:
            mail.attach_alternative(html_message, 'text/html')
        mail.send(using=self.using)
