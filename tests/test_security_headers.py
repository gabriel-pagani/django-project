import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_login_page_carries_the_security_headers(client):
    response = client.get(reverse('admin:login'))

    assert 'camera=()' in response['Permissions-Policy']

    csp = response['Content-Security-Policy']
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
