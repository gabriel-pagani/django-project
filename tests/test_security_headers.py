import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse

from project.middleware import PermissionsPolicyMiddleware


@pytest.mark.django_db
def test_login_page_carries_the_security_headers(client):
    response = client.get(reverse('app:login'))

    assert 'camera=()' in response['Permissions-Policy']

    csp = response['Content-Security-Policy']
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp


def test_view_that_sets_its_own_policy_keeps_it():
    def view(request):
        response = HttpResponse()
        response['Permissions-Policy'] = 'camera=(self)'
        return response

    response = PermissionsPolicyMiddleware(view)(RequestFactory().get('/'))

    assert response['Permissions-Policy'] == 'camera=(self)'
