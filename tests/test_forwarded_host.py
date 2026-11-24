from django.test import RequestFactory


# O nginx já repassa o Host original; o X-Forwarded-Host é escrito pelo cliente
# e não pode decidir o domínio dos links que o sistema gera.
def test_ignores_the_host_the_client_writes():
    request = RequestFactory().get('/', HTTP_HOST='localhost', HTTP_X_FORWARDED_HOST='evil.example')

    assert request.get_host() == 'localhost'
