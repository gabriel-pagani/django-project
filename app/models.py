from django.db import models
from django.contrib.auth.models import AbstractUser, Group as BaseGroup
from django.db.models.functions import Lower
from django.utils.crypto import salted_hmac


class User(AbstractUser):
    email = models.EmailField(blank=True, null=True, verbose_name='Endereço de email')
    observations = models.TextField(blank=True, null=True, verbose_name='Observações')
    # As sessões ficam no cache, sem índice por usuário: para derrubar as de
    # alguém, este número entra no hash que o Django confere a cada requisição
    session_version = models.PositiveIntegerField(default=0, editable=False)

    def clean(self):
        super().clean()
        # Vazio vira nulo para não colidir na regra de único.
        self.email = self.email or None

    class Meta(AbstractUser.Meta):
        # No banco, e não numa consulta no clean(): dois cadastros ao mesmo tempo
        # passariam os dois pela consulta.
        constraints = [
            models.UniqueConstraint(
                Lower('email'),
                condition=models.Q(email__isnull=False) & ~models.Q(email=''),
                name='user_unique_email_case_insensitive',
                violation_error_message='Já existe um usuário com este e-mail.',
            ),
        ]

    def _get_session_auth_hash(self, secret=None):
        # Na versão 0 o hash é o de sempre, para quem já está logado não cair
        # quando o campo chegar
        if not self.session_version:
            return super()._get_session_auth_hash(secret=secret)
        key_salt = f'app.User.get_session_auth_hash.{self.session_version}'
        return salted_hmac(key_salt, self.password, secret=secret, algorithm='sha256').hexdigest()


class Group(BaseGroup):
    class Meta:
        proxy = True
        verbose_name = BaseGroup._meta.verbose_name
        verbose_name_plural = BaseGroup._meta.verbose_name_plural
        app_label = 'app'
