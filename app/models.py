from django.db import models
from django.contrib.auth.models import AbstractUser, Group as BaseGroup
from django.db.models.functions import Lower


class User(AbstractUser):
    email = models.EmailField(blank=True, null=True, verbose_name='Endereço de email')
    observations = models.TextField(blank=True, null=True, verbose_name='Observações')

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


class Group(BaseGroup):
    class Meta:
        proxy = True
        verbose_name = BaseGroup._meta.verbose_name
        verbose_name_plural = BaseGroup._meta.verbose_name_plural
        app_label = 'app'
