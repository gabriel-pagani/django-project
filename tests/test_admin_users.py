import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from tests.conftest import sign_in


User = get_user_model()


@pytest.mark.django_db
def test_admin_desativa_os_usuarios_selecionados(client):
    sign_in(client, User.objects.create_superuser(username='admin', password='senha'))
    first = User.objects.create_user(username='primeiro', password='senha')
    second = User.objects.create_user(username='segundo', password='senha')
    already_inactive = User.objects.create_user(username='inativo', password='senha', is_active=False)

    response = client.post(reverse('admin:app_user_changelist'), {
        'action': 'deactivate_users',
        '_selected_action': [first.pk, second.pk, already_inactive.pk],
        'index': '0',
    }, follow=True)

    assert response.status_code == 200
    assert not User.objects.filter(pk__in=[first.pk, second.pk, already_inactive.pk], is_active=True).exists()
    # O que já estava inativo não entra na conta.
    assert '2 usuário(s) desativado(s) com sucesso.' in response.content.decode()
