"""
Com DEBUG desligado, os erros do Django aparecem no log do container.
"""
import logging
from unittest.mock import patch


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
