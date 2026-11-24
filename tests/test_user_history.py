import pytest
import reversion
from reversion.models import Version

from app.models import User


# Reverter ou recuperar uma versão antiga devolveria a senha antiga, mesmo a
# que foi trocada por ter vazado.
@pytest.mark.django_db
def test_historico_do_usuario_nao_guarda_a_senha():
    with reversion.create_revision():
        user = User.objects.create_user('ana', password='s3nha-forte-123')

    data = Version.objects.get_for_object(user).get().field_dict

    assert data['username'] == 'ana'
    assert 'password' not in data
    assert 'last_login' not in data
