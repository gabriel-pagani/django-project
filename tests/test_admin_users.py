import re

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from app.models import Group
from app.utils.permissions_report import permissions_report_pdf, user_permissions_report
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


@pytest.fixture
def report_users(db):
    group = Group.objects.create(name='Suporte')
    view_user = Permission.objects.get(content_type__app_label='app', codename='view_user')
    change_user = Permission.objects.get(content_type__app_label='app', codename='change_user')
    group.permissions.add(view_user, change_user)

    operator = User.objects.create_user(username='operador', password='senha', first_name='Ana & <Cia>', is_active=False)
    operator.groups.add(group)
    operator.user_permissions.add(view_user)
    User.objects.create_user(username='sem-acesso', password='senha')
    User.objects.create_superuser(username='admin', password='senha')
    return User.objects.all()


def test_relatorio_mostra_de_onde_vem_cada_permissao(report_users):
    report = {item['user'].username: item for item in user_permissions_report(report_users)}
    assert list(report) == ['admin', 'operador', 'sem-acesso']

    permissions = {row['codename']: row['sources'] for row in report['operador']['permissions']}
    assert permissions == {
        'app.change_user': ['Grupo Suporte'],
        'app.view_user': ['Direta', 'Grupo Suporte'],
    }
    assert report['operador']['groups'] == ['Suporte']
    assert report['sem-acesso']['permissions'] == []
    # O superusuário aparece com todas as permissões do sistema, cada uma com a origem dele
    assert len(report['admin']['permissions']) == Permission.objects.count()
    assert {tuple(row['sources']) for row in report['admin']['permissions']} == {('Superusuário',)}


def test_acao_do_relatorio_baixa_um_pdf(client, report_users):
    sign_in(client, User.objects.get(username='admin'))

    response = client.post(reverse('admin:app_user_changelist'), {
        'action': 'permissions_report',
        '_selected_action': [user.pk for user in report_users],
        'index': '0',
    })

    assert response.status_code == 200
    assert response['Content-Type'] == 'application/pdf'
    assert response['Content-Disposition'].startswith('attachment; filename="relatorio-permissoes-')
    # O nome com & e < chega escapado à ReportLab: sem isso, o PDF nem seria gerado
    assert response.content.startswith(b'%PDF')


@pytest.mark.django_db
def test_relatorio_comeca_o_usuario_na_primeira_pagina():
    user = User.objects.create_user(username='operador', password='senha')
    user.user_permissions.add(*Permission.objects.order_by('pk')[:40])

    pdf = permissions_report_pdf(user_permissions_report(User.objects.all()), 'admin')

    # Uma tabela que não cabe no resto da página começa nela e continua na seguinte:
    # empurrada inteira para a página 2, a primeira ficava só com o título do relatório
    assert re.search(rb'/Count (\d+)', pdf).group(1) == b'2'
