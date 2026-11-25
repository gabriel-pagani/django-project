from django.test import RequestFactory

from app.utils.get_ip import get_client_ip


# O nginx já repassa o Host original; o X-Forwarded-Host é escrito pelo cliente
# e não pode decidir o domínio dos links que o sistema gera.
def test_ignores_the_host_the_client_writes():
    request = RequestFactory().get('/', HTTP_HOST='localhost', HTTP_X_FORWARDED_HOST='evil.example')

    assert request.get_host() == 'localhost'


# É deste IP que o axes conta as tentativas: o nginx põe o do cliente no
# X-Real-IP, e o REMOTE_ADDR seria sempre o do próprio nginx.
def test_client_ip_comes_from_the_nginx_header():
    request = RequestFactory().get('/', HTTP_X_REAL_IP=' 203.0.113.7 ', REMOTE_ADDR='172.18.0.5')

    assert get_client_ip(request) == '203.0.113.7'


def test_without_the_nginx_header_the_ip_is_the_connection_one():
    request = RequestFactory().get('/', REMOTE_ADDR='172.18.0.5')

    assert get_client_ip(request) == '172.18.0.5'
