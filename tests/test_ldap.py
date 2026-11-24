"""O backend do AD só entra na fila quando há servidor configurado."""
import runpy
from pathlib import Path

from django.conf import settings

SETTINGS = Path(settings.BASE_DIR) / 'project' / 'settings.py'
LDAP = 'django_auth_ldap.backend.LDAPBackend'


def test_sem_servidor_o_ldap_fica_de_fora(monkeypatch):
    monkeypatch.delenv('AUTH_LDAP_SERVER_URI', raising=False)
    assert LDAP not in runpy.run_path(str(SETTINGS))['AUTHENTICATION_BACKENDS']


def test_com_servidor_o_ldap_entra_por_ultimo(monkeypatch):
    monkeypatch.setenv('AUTH_LDAP_SERVER_URI', 'ldaps://ad.exemplo.com')
    assert runpy.run_path(str(SETTINGS))['AUTHENTICATION_BACKENDS'][-1] == LDAP


def test_grupo_de_admin_do_ad_da_superusuario(monkeypatch):
    monkeypatch.setenv('ADMIN_GROUP_DN', 'cn=admins,dc=exemplo,dc=com')
    flags = runpy.run_path(str(SETTINGS))['AUTH_LDAP_USER_FLAGS_BY_GROUP']
    assert flags['is_superuser'] == 'cn=admins,dc=exemplo,dc=com'
    assert 'cn=admins,dc=exemplo,dc=com' in flags['is_staff']
