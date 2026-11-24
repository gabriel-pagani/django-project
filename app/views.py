from datetime import datetime, timedelta
from app.forms import LoginForm
from app.models import User
from app.utils import otp, throttle
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from axes.handlers.proxy import AxesProxyHandler
from django_otp import login as otp_login, match_token


LOGIN_THROTTLED_ERROR = 'Muitas tentativas de login. Espere uma hora e tente novamente.'

TOKEN_INVALID_ERROR = 'Código inválido! Digite o código que o aplicativo mostra agora.'

# Entre a senha e o código o usuário fica guardado na sessão, e só isso: a
# sessão segue anônima, e nada do sistema abre com essa espera na mão.
PENDING_LOGIN = 'otp_pending'

# Tempo para digitar o código. Vencido, a senha é pedida de novo: a espera não
# pode virar meia sessão esquecida num computador emprestado.
PENDING_LOGIN_TIMEOUT = timedelta(minutes=5)


def login_throttled(request, username):
    # A recusa por teto de tentativas chega igual à de senha errada: os dois
    # tetos interrompem a fila de backends, e o authenticate devolve None.
    # Quem espera uma hora precisa saber por quê, e saber que o teto estourou
    # não conta nada sobre a conta que já não se soubesse.
    return throttle.login_blocked(username) or not AxesProxyHandler.is_allowed(request, {'username': username})


def get_safe_next_url(request, next_url):
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return None


@login_required
def home_view(request):
    return render(request, 'app/app.html')


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        next_url = get_safe_next_url(request, request.POST.get('next'))

        if form.is_valid():
            username = form.cleaned_data.get('username', '')
            # O request vai junto: é dele que o axes tira o IP para contar as
            # tentativas, e sem ele o teto por usuário e IP não existe.
            user = authenticate(
                request,
                username=username,
                password=form.cleaned_data.get('password', ''),
            )

            if user is not None:
                # Administrador com aplicativo cadastrado só entra com o código.
                # O que ainda não cadastrou entra e é levado ao cadastro pelo
                # RequireOTPMiddleware, antes de chegar a qualquer tela.
                if otp.requires_otp(user) and otp.confirmed_device(user):
                    request.session[PENDING_LOGIN] = {
                        'user': user.pk,
                        # O backend que conferiu a senha, para o login entrar pelo
                        # mesmo: o do LDAP e o local guardam a sessão diferente.
                        'backend': user.backend,
                        'next': next_url,
                        'since': timezone.now().isoformat(),
                    }
                    return redirect('app:login-token')

                login(request, user)
                return redirect(next_url or reverse('app:home'))
            elif login_throttled(request, username):
                messages.error(request, LOGIN_THROTTLED_ERROR)
            else:
                messages.error(request, 'Dados inválidos!')
        else:
            messages.error(request, 'Preencha todos os campos!')
    else:
        # Abrir a tela da senha é recomeçar: a espera de código que sobrou de
        # outra tentativa não vale mais.
        request.session.pop(PENDING_LOGIN, None)
        form = LoginForm()
        next_url = get_safe_next_url(request, request.GET.get('next'))

    return render(request, 'app/login.html', {
        'form': form,
        'next': next_url
    })


def pending_login(request):
    """Quem já passou pela senha e ainda deve o código; None se não há ou venceu."""
    data = request.session.get(PENDING_LOGIN)
    if not data:
        return None

    if timezone.now() - datetime.fromisoformat(data['since']) > PENDING_LOGIN_TIMEOUT:
        del request.session[PENDING_LOGIN]
        return None

    # Relido do banco: entre uma etapa e outra a conta pode ter sido desativada.
    return User.objects.filter(pk=data['user'], is_active=True).first()


def login_token_view(request):
    user = pending_login(request)
    if user is None:
        return redirect('app:login')

    if request.method == 'POST':
        # O match_token segura a repetição: cada código errado dobra a espera
        # até o próximo palpite ser conferido.
        device = match_token(user, request.POST.get('token', '').strip())

        if device is not None:
            data = request.session.pop(PENDING_LOGIN)
            login(request, user, backend=data['backend'])
            otp_login(request, device)
            return redirect(data['next'] or reverse('app:home'))

        messages.error(request, TOKEN_INVALID_ERROR)

    return render(request, 'app/login_token.html')


@login_required
def otp_setup_view(request):
    """
    O cadastro do aplicativo autenticador, no primeiro login do administrador.

    O segredo só é confirmado quando a pessoa devolve um código gerado por ele:
    assim ninguém fica com um segundo fator que nunca conseguiu usar.
    """
    user = request.user

    # Um segundo dispositivo deixaria dois segredos válidos para a mesma conta.
    # Para trocar de celular, apague o dispositivo no portal de administração.
    if not otp.requires_otp(user) or otp.confirmed_device(user):
        return redirect('app:home')

    device = otp.pending_device(user)

    if request.method == 'POST':
        if device.verify_token(request.POST.get('token', '').strip()):
            device.confirmed = True
            device.save(update_fields=['confirmed'])
            # A pessoa acabou de provar que tem o aplicativo: pedir o código de
            # novo agora seria só atrito.
            otp_login(request, device)
            return redirect('app:home')

        messages.error(request, TOKEN_INVALID_ERROR)

    return render(request, 'app/otp_setup.html', {
        'qr': otp.qr_of(device),
        'secret': otp.secret_of(device),
    })


# Só por POST: um link ou uma imagem de outro site não pode encerrar a sessão.
@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, 'Você se desconectou com sucesso!')
    return redirect('app:login')
