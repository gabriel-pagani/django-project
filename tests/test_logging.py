"""
Com DEBUG desligado, os erros do Django aparecem no log do container e chegam por e-mail a quem é
superusuário e equipe no cadastro.
"""
import logging
from unittest.mock import patch

import pytest


@pytest.mark.django_db
def test_erro_do_django_chega_no_console_sem_debug(settings):
    assert not settings.DEBUG
    console = next(h for h in logging.getLogger().handlers if type(h) is logging.StreamHandler)
    with patch.object(console, 'emit') as emit:
        logging.getLogger('django.request').error('Internal Server Error: /x')
    emit.assert_called_once()


def test_inicio_do_axes_nao_vai_para_o_log():
    # Um comando agendado carrega o Django a cada execução; o anúncio do axes entupiria o log.
    assert not logging.getLogger('axes.apps').isEnabledFor(logging.INFO)
    assert logging.getLogger('axes.handlers').isEnabledFor(logging.INFO)


@pytest.mark.django_db
def test_erro_500_vai_por_email_a_quem_e_superusuario_e_equipe(settings, mailoutbox, django_user_model):
    django_user_model.objects.create(username='admin', email='admin@example.com', is_superuser=True, is_staff=True)
    django_user_model.objects.create(username='equipe', email='equipe@example.com', is_staff=True)
    django_user_model.objects.create(username='super', email='super@example.com', is_superuser=True)
    django_user_model.objects.create(username='inativo', email='inativo@example.com',
                                     is_superuser=True, is_staff=True, is_active=False)
    django_user_model.objects.create(username='semmail', is_superuser=True, is_staff=True)
    logging.getLogger('django.request').error('Internal Server Error: /x')
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ['admin@example.com']
    assert mailoutbox[0].from_email == settings.DEFAULT_FROM_EMAIL


@pytest.mark.django_db
def test_sem_superusuario_com_email_nao_manda_nada(mailoutbox):
    logging.getLogger('django.request').error('Internal Server Error: /x')
    assert mailoutbox == []
