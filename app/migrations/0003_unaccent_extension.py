from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_user_unique_email_case_insensitive'),
    ]

    # O unaccent é uma extensão "trusted": o usuário do app, dono do banco, cria
    # sem precisar ser superusuário.
    operations = [
        UnaccentExtension(),
    ]
