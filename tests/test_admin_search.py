import pytest
from django.contrib.admin.sites import site

from app.admin import GroupAdmin, UserAdmin
from app.models import Group, User


# A busca do painel roda pelo get_search_results do próprio admin, que é onde o
# acento é tratado; entrar pela URL exigiria sessão com o segundo fator conferido.
def search(admin_class, model, term):
    results, _ = admin_class(model, site).get_search_results(None, model.objects.all(), term)
    return list(results)


@pytest.mark.django_db
def test_busca_sem_acento_acha_o_nome_com_acento():
    user = User.objects.create(username='jose', first_name='José', last_name='Conceição')
    assert search(UserAdmin, User, 'jose conceicao') == [user]


@pytest.mark.django_db
def test_busca_com_acento_continua_achando_o_mesmo_nome():
    user = User.objects.create(username='jose', first_name='José', last_name='Conceição')
    assert search(UserAdmin, User, 'CONCEIÇÃO') == [user]


@pytest.mark.django_db
def test_busca_de_grupo_ignora_acento():
    group = Group.objects.create(name='Logística')
    assert search(GroupAdmin, Group, 'logistica') == [group]


@pytest.mark.django_db
def test_busca_que_nao_casa_com_nada_fica_vazia():
    User.objects.create(username='jose', first_name='José')
    assert search(UserAdmin, User, 'mariana') == []
