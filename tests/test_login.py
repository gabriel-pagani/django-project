import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from app.models import User
from app.views import LOGIN_THROTTLED_ERROR


# O client.login() não serve aqui: ele chama o authenticate() sem request, e o
# backend do axes exige o request para saber de qual IP veio a tentativa. Estes
# testes entram pela tela, que é por onde as pessoas entram.
def attempt(client, username='operador', password='senha'):
    return client.post(reverse('app:login'), {'username': username, 'password': password})


def messages_of(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


@pytest.fixture
def user(db):
    return User.objects.create_user(username='operador', password='senha')


@pytest.mark.django_db
def test_login_redirects_to_home(client, user):
    response = attempt(client)
    assert response.status_code == 302
    assert response.url == reverse('app:home')


@pytest.mark.django_db
def test_wrong_password_does_not_say_which_field_failed(client, user):
    response = attempt(client, password='errada')
    assert messages_of(response) == ['Dados inválidos!']


@pytest.mark.django_db
def test_axes_blocks_the_pair_after_the_failure_limit(client, settings, user):
    for _ in range(settings.AXES_FAILURE_LIMIT):
        attempt(client, password='errada')

    response = attempt(client)

    assert messages_of(response) == [LOGIN_THROTTLED_ERROR]
    assert client.session.get('_auth_user_id') is None
