# django-project

Modelo para começar um sistema Django novo, pronto para produção. Tudo roda em Docker: Postgres, Redis, Django com Gunicorn, nginx e um túnel da Cloudflare, que publica o sistema sem abrir nenhuma porta no servidor.

O que já vem pronto:

- Login em duas etapas. Quem é da equipe (`is_staff` ou superusuário) digita um código TOTP depois da senha; usuário comum entra só com a senha.
- Três limites de tentativas de login:
  - o do nginx, por IP;
  - o do axes, por usuário e IP;
  - um teto por usuário, que vale de qualquer rede.
  
  Por cima deles, a Cloudflare pode exigir um desafio na tela de login (opcional).
- Login pelo Active Directory (LDAP), ligado só quando há servidor configurado.
- Cabeçalhos de segurança (CSP, Permissions-Policy, HSTS), cookies `__Host-` e Redis com senha.
- Banco e Redis numa rede interna, que o nginx e o túnel não alcançam.
- O app entra no banco com um usuário do Postgres sem poder de superusuário.
- Erros 500 no log dos containers e por e-mail para quem é superusuário e equipe no cadastro.
- No painel, busca que ignora acento e ações para desativar usuários em lote e gerar um PDF com as permissões de cada um e de onde elas vêm.
- Backups com conferência de restauração, tarefas agendadas e testes no Docker e no CI.
- Deploy automático pelo GitHub Actions e atualizações de dependências pelo Dependabot.

## Sumário

1. [Requisitos](#requisitos)
2. [Começando um projeto novo](#começando-um-projeto-novo)
3. [Variáveis do deploy/.env](#variáveis-do-deployenv)
4. [Cloudflare: túnel](#cloudflare-túnel)
5. [Cloudflare: desafio no login (WAF)](#cloudflare-desafio-no-login-waf)
6. [Primeira subida no servidor](#primeira-subida-no-servidor)
7. [Deploy automático pelo GitHub Actions](#deploy-automático-pelo-github-actions)
8. [Dependabot](#dependabot)
9. [Login e verificação em duas etapas](#login-e-verificação-em-duas-etapas)
10. [Active Directory (opcional)](#active-directory-opcional)
11. [Backups](#backups)
12. [Tarefas agendadas](#tarefas-agendadas)
13. [Testes](#testes)
14. [Desenvolvimento local](#desenvolvimento-local)
15. [Comandos do Makefile](#comandos-do-makefile)

## Requisitos

- **Servidor:** Linux amd64 com Docker e Docker Compose v2, `make` e `git`. O agendador (supercronic) vem só na versão amd64.
- **Domínio:** gerenciado pela Cloudflare, mesmo no plano gratuito.
- **Repositório no GitHub:** necessário para o CI, o deploy automático e o Dependabot.
- **SMTP:** opcional; serve para receber os erros 500 por e-mail.

No Windows, use o Git Bash para rodar o `make`.

## Começando um projeto novo

1. Copie este repositório: "Use this template" no GitHub, ou clone e troque o `origin`.
2. Crie o arquivo de configuração a partir do exemplo:
   ```sh
   cp deploy/.env.example deploy/.env
   ```
3. Preencha o `deploy/.env` (veja a [próxima seção](#variáveis-do-deployenv)). Gere os segredos com:
   ```sh
   openssl rand -hex 32
   ```
4. Crie o túnel na Cloudflare e cole o token no `.env` ([Cloudflare: túnel](#cloudflare-túnel)).
5. Suba o sistema no servidor ([Primeira subida no servidor](#primeira-subida-no-servidor)).
6. Opcional: configure o [desafio no login](#cloudflare-desafio-no-login-waf) e o [deploy automático](#deploy-automático-pelo-github-actions).

> **O `deploy/.env` nunca vai para o git.** Ele guarda as senhas do banco, o token do túnel e as chaves de API. O `.gitignore` e o `.dockerignore` já o deixam de fora.

## Variáveis do deploy/.env

| Variável | Para que serve |
|---|---|
| `PROJECT_NAME` | Nome do projeto no Docker: aparece no nome dos containers, das imagens e dos volumes. Use um nome único em cada servidor. |
| `SECRET_KEY` | Chave do Django. Longa, aleatória e diferente em cada projeto. |
| `DEBUG` | `0` em produção. Com `1`, o Django deixa de exigir HTTPS. |
| `ALLOWED_HOSTS` | Domínios do sistema, separados por vírgula (`app.exemplo.com`). |
| `CSRF_TRUSTED_ORIGINS` | Os mesmos domínios, com `https://` (`https://app.exemplo.com`). |
| `ADMIN_PANEL_PATH` | Caminho do painel de administração (`painel-interno`), para não ficar no `/admin` que todo robô tenta. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Banco e superusuário do Postgres, criados junto com o volume. Só o Postgres e os scripts de manutenção usam esse usuário. |
| `POSTGRES_APP_USER`, `POSTGRES_APP_PASSWORD` | Usuário restrito com que o Django entra no banco, criado pelo `make create-app-role`. Precisa ser diferente do `POSTGRES_USER`. |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Mantenha `postgres` e `5432`. |
| `REDIS_URL` | Mantenha `redis://redis:6379/0`. |
| `REDIS_PASSWORD` | Senha do Redis, que guarda as sessões. **Obrigatória**: sem ela o compose não sobe. |
| `CLOUDFLARE_TOKEN` | Token do túnel ([Cloudflare: túnel](#cloudflare-túnel)). |
| `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ZONE_ID` | Só para o `make protect-login` ([desafio no login](#cloudflare-desafio-no-login-waf)). Deixe vazio se não for usar. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_TIMEOUT` | Servidor SMTP. Para não enviar nada de verdade, acrescente `EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"`, que só escreve os e-mails no log. |
| `DEFAULT_FROM_EMAIL` | Remetente dos e-mails do sistema, inclusive os de erro. |
| `AUTH_LDAP_*`, `STAFF_GROUP_DN` | Login pelo Active Directory ([Active Directory](#active-directory-opcional)). O `AUTH_LDAP_SERVER_URI` vem vazio, com o AD desligado. **Só preencha se for usar AD:** com qualquer valor ali, o login tenta o AD. |

> **Variável nova no `settings.py`:** acrescente-a também à lista `environment` do serviço `django` no [deploy/docker-compose.yml](deploy/docker-compose.yml). Cada serviço recebe só as variáveis listadas para ele, e o que não está na lista não chega ao container.

## Cloudflare: túnel

O túnel faz o servidor abrir uma conexão de saída até a Cloudflare, e as visitas chegam por ela. O servidor não precisa de IP público nem de porta aberta, e o HTTPS termina na Cloudflare. O serviço `cloudflare` do compose é quem roda o conector.

1. No painel da Cloudflare, abra **Zero Trust → Networks → Tunnels → Create a tunnel** e escolha **Cloudflared**. Em painéis mais novos, o caminho é **Networks → Connectors → Cloudflare Tunnels**.
2. Dê um nome ao túnel (por exemplo, o `PROJECT_NAME`).
3. Na tela de instalação, copie só o token: o texto longo depois de `--token` no comando mostrado. Cole-o em `CLOUDFLARE_TOKEN` no `deploy/.env`. Não rode o comando de instalação, porque o conector já está no compose.
4. Em **Public Hostname** (ou **Published application routes**, nos painéis mais novos), adicione:
   - **Subdomain/Domain:** o endereço do sistema (o mesmo do `ALLOWED_HOSTS`);
   - **Service:** `HTTP`, URL `nginx:80`.
5. Salve. O túnel aparece como *Healthy* quando o sistema estiver no ar.

Para mais de um endereço, adicione um Public Hostname por endereço. Inclua cada um no `ALLOWED_HOSTS` e no `CSRF_TRUSTED_ORIGINS`.

> **Cuidado com o token do túnel.** Com o token, qualquer pessoa roda um conector próprio, e esse conector passa a receber parte das visitas reais: senhas, códigos e cookies. Por isso só o serviço `cloudflare` recebe esse token. Se ele vazar, gere outro na página do túnel (**Refresh token**).

> **Não suba o serviço `cloudflare` na sua máquina** com o token de produção: ela passaria a atender parte das visitas do sistema real. Para testar localmente, veja [Desenvolvimento local](#desenvolvimento-local).

### HTTPS e HSTS

Em produção (`DEBUG=0`), o Django redireciona para HTTPS e envia HSTS por um ano, com `includeSubDomains` e `preload`. Na Cloudflare, ative **SSL/TLS → Edge Certificates → Always Use HTTPS**.

O `includeSubDomains` obriga os navegadores a usar HTTPS em **todos** os subdomínios do domínio, por um ano. Antes de publicar, confirme que nenhum subdomínio ainda depende de HTTP. Se algum depende, tire `SECURE_HSTS_INCLUDE_SUBDOMAINS` e `SECURE_HSTS_PRELOAD` do [project/settings.py](project/settings.py).

## Cloudflare: desafio no login (WAF)

Os limites do nginx e do axes contam por IP, e quem ataca com uma lista de endereços recomeça a conta em cada um. O `make protect-login` cria uma regra no WAF da Cloudflare: o navegador resolve um desafio (*managed challenge*) antes de chegar à tela de login e à do painel. Para quem usa o sistema, o desafio costuma ser invisível. Para robôs, cada tentativa fica cara.

1. Crie um token de API em **My Profile → API Tokens → Create Token → Create Custom Token**:
   - **Permissions:** `Zone` → `Zone WAF` → `Edit`;
   - **Zone Resources:** `Include` → `Specific zone` → o seu domínio.
   
   Este token é diferente do token do túnel.
2. Copie o **Zone ID**. Ele fica na página do domínio (**Overview**), na coluna da direita, em *API*.
3. Preencha `CLOUDFLARE_API_TOKEN` e `CLOUDFLARE_ZONE_ID` no `deploy/.env`.
4. Rode:
   ```sh
   make protect-login
   ```
   A regra vale só para os domínios do `ALLOWED_HOSTS` e cobre `/login`, `/login/token` e `/<ADMIN_PANEL_PATH>/login`.
5. Entre no sistema para conferir. Se a tela de login travar, desfaça com:
   ```sh
   make protect-login args=remove
   ```

Rodar de novo é seguro: a regra é encontrada pela descrição (`<PROJECT_NAME>: desafio nas telas de entrada`) e atualizada no lugar, sem mexer nas outras regras do domínio.

## Primeira subida no servidor

```sh
git clone <repositório> && cd <pasta>
cp deploy/.env.example deploy/.env    # e preencha
make build backup=no         # na 1ª vez ainda não há banco para copiar
make create-app-role         # cria o usuário do app no Postgres
make create-superuser        # cria o administrador e mostra o QR Code do TOTP
```

Até o `make create-app-role` rodar, o container `django` fica reiniciando, com `password authentication failed` no log (`make logs container=django`). Isso é esperado num banco novo. Quando o usuário existe, o django sobe sozinho e roda as migrations.

O `make create-superuser` pede usuário e senha e depois mostra no terminal o QR Code do aplicativo autenticador (Google Authenticator, Aegis, 1Password...). Escaneie e guarde a chave em lugar seguro: sem ela e sem o aplicativo, o acesso ao painel se perde.

Nas próximas atualizações, basta um `make build`. Ele faz um backup, baixa as versões novas das imagens, reconstrói e sobe tudo.

## Deploy automático pelo GitHub Actions

O workflow [.github/workflows/cicd-pipeline.yaml](.github/workflows/cicd-pipeline.yaml) roda em todo push e pull request para a `main`. Ele:
- confere as dependências contra vulnerabilidades conhecidas;
- confere se falta alguma migration;
- roda os testes.

O job `deploy` vem depois dos testes, só em push para a `main`. Ele roda no próprio servidor, por um runner self-hosted, porque o túnel não deixa o GitHub entrar por SSH. Cada deploy gera um backup e confere se ele restaura.

O job fica desligado até as duas variáveis do passo 5 existirem. Para ligar:

1. No GitHub: **Settings → Actions → Runners → New self-hosted runner** (Linux, x64).
2. No servidor, numa pasta **fora** do projeto (por exemplo, `~/actions-runner`), rode os comandos que o GitHub mostrar.
   - No `./config.sh`, informe uma label própria em *additional labels*, por exemplo o `PROJECT_NAME`.
   - Se aparecer *Libicu's dependencies is missing*, rode `sudo ./bin/installdependencies.sh` e repita o `config.sh`. O token de registro vale uma hora.
3. Em vez do `./run.sh`, instale o runner como serviço:
   ```sh
   sudo ./svc.sh install $USER && sudo ./svc.sh start
   ```
4. O usuário do runner precisa estar no grupo `docker`, e o `git pull` na pasta do projeto precisa funcionar sem pedir senha (deploy key ou HTTPS com credencial salva).
5. Em **Settings → Secrets and variables → Actions → Variables**, crie:
   - `DEPLOY_PATH`: a pasta do projeto no servidor (por exemplo, `/home/usuario/sites/meu-projeto`);
   - `RUNNER_LABEL`: a label do passo 2.

> **Repositório público:** em **Settings → Actions → General**, marque *Require approval for all external contributors*. Sem isso, um pull request de fork pode trocar o `runs-on` de um job para o runner do servidor e executar código nele. Com o usuário no grupo `docker`, isso equivale a acesso de root.

## Dependabot

O [.github/dependabot.yml](.github/dependabot.yml) abre pull requests toda semana com versões novas de:
- pacotes Python;
- imagens Docker;
- actions do GitHub.

Ele não propõe:
- **Postgres em outra versão principal:** trocar a versão principal exige migrar o volume de dados;
- **nginx com número menor ímpar:** é a linha de desenvolvimento, não a estável.

Para receber também os alertas de segurança, ative **Settings → Code security** (ou **Advanced Security**) **→ Dependabot alerts** e **Dependabot security updates**.

Tags como `postgres:18` e `redis:8-alpine` recebem correções sem mudar de nome, e o Dependabot não as vê. O `make build` baixa essas imagens de novo a cada deploy.

O supercronic, no [deploy/Dockerfile](deploy/Dockerfile), está fixo numa versão e num checksum e é atualizado à mão.

## Login e verificação em duas etapas

| Quem | Como entra |
|---|---|
| Usuário comum | Usuário e senha em `/login/`. |
| Equipe (`is_staff` ou superusuário) | Senha em `/login/`, depois o código do aplicativo em `/login/token/`. No primeiro login, cadastra o aplicativo pelo QR Code em `/two-factor/`, sem conseguir abrir nenhuma outra tela antes disso. |

O painel de administração (`/<ADMIN_PANEL_PATH>/`) passa pela mesma tela de login e exige o código.

- **Trocar de celular:** no painel, apague o dispositivo da pessoa em *TOTP devices*. No próximo login, ela cadastra o aplicativo de novo. Pelo terminal, a mesma coisa sai com `make create-totp user=<usuário>`, depois de apagar o dispositivo antigo.
- **Tentativas erradas:** o axes tranca o par usuário + IP por uma hora depois de 5 erros. O teto por usuário tranca a conta depois de 50 erros numa hora, vindos de qualquer rede, e zera no primeiro acerto. Para destrancar um par do axes antes da hora, apague a tentativa em *Access attempts*, no painel.

## Active Directory (opcional)

Preencha as variáveis `AUTH_LDAP_*` no `deploy/.env`:
- `AUTH_LDAP_SERVER_URI`: `ldaps://servidor`;
- `AUTH_LDAP_BIND_DN` e `AUTH_LDAP_BIND_PASSWORD`: uma conta de serviço com permissão de leitura;
- `AUTH_LDAP_USER_SEARCH` e `AUTH_LDAP_GROUP_SEARCH`: as OUs onde ficam os usuários e os grupos.

O login aceita o `sAMAccountName`. A cada entrada, o sistema copia do AD o nome, o e-mail e os grupos.

Quem está no grupo `STAFF_GROUP_DN` vira `is_staff`. Superusuário nunca vem do AD, para que mexer num grupo não dê acesso total ao sistema: ele é marcado à mão, no painel.

Sem `AUTH_LDAP_SERVER_URI`, o AD fica de fora e só valem os usuários locais.

## Backups

```sh
make backup         # banco (.sql) + arquivos enviados (media-*.tar.gz) em backups/
make check-backup   # restaura o .sql mais recente num Postgres descartável e mostra o que voltou
make check-backup file=backups/20260101-000000.sql
```

Os backups ficam em `backups/`, legíveis só pelo dono, porque o dump contém os hashes das senhas. Eles **não saem do servidor**: copie-os para fora (outro disco, nuvem) por conta própria.

Para um backup diário, agende no cron do servidor:
```cron
0 0 * * * cd /caminho/do/projeto && make backup >> backups/backup.log 2>&1
```

**Restaurar:** suba um banco vazio e rode:
```sh
make restore-database file=backups/<arquivo>.sql
make create-app-role    # o dump volta com as tabelas do superusuário
```

## Tarefas agendadas

O serviço `scheduler` roda os comandos do [deploy/crontab](deploy/crontab) com o supercronic, no horário de Brasília. Tarefa nova é uma linha no arquivo, seguida de `make build`:

```cron
# minuto hora dia mês dia-da-semana comando
30 2 * * * python manage.py meu_comando
```

Já vem agendada a limpeza diária do log de acesso do axes (registros com mais de 30 dias).

## Testes

```sh
make run-tests                                     # a suíte inteira, no Docker
make run-tests args="tests/test_otp.py -k setup"   # só uma parte
```

- Depois de mudar o `requirements.txt`, reconstrua a imagem dos testes:
  ```sh
  docker compose -f deploy/docker-compose.yml build tests
  ```
- Os testes usam o banco do compose (com um banco de testes próprio) e um cache em memória, então não tocam nas sessões reais do Redis.
- O CI roda a mesma suíte a cada push.

## Desenvolvimento local

O nginx não publica nenhuma porta: em produção, só o túnel chega até ele. Na sua máquina, suba o Django com o servidor de desenvolvimento, sem o túnel.

Na primeira vez, prepare o banco:

```sh
docker compose -f deploy/docker-compose.yml up -d --wait postgres redis
make create-app-role
docker compose -f deploy/docker-compose.yml run --rm django python manage.py migrate
```

Depois, sempre que for trabalhar:

```sh
docker compose -f deploy/docker-compose.yml run --rm -p 127.0.0.1:8000:8000 \
  -e DEBUG=1 -e ALLOWED_HOSTS=127.0.0.1,localhost -e CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000 \
  -v "$PWD/app:/app/app" -v "$PWD/project:/app/project" \
  -v "$PWD/templates:/app/templates" -v "$PWD/static:/app/static" \
  django python manage.py runserver 0.0.0.0:8000
```

Abra http://127.0.0.1:8000. As pastas montadas fazem a mudança no código aparecer na hora. O comando também sobe o Postgres e o Redis, se ainda não estiverem no ar.

No Git Bash do Windows, ponha `MSYS_NO_PATHCONV=1` antes do comando e troque `$PWD` por `$(pwd -W)`.

**Migrations novas:**
```sh
make migrations app=app
```
Depois do `make build`, as migrations rodam sozinhas.

## Comandos do Makefile

| Comando | O que faz |
|---|---|
| `make build` | Backup, baixa as imagens novas, reconstrói e sobe tudo. `backup=no` pula o backup. |
| `make start` / `stop` / `restart` | Sobe, para e reinicia os containers. **Sobe também o túnel.** |
| `make reset-cache` | Esvazia o Redis: todo mundo precisa entrar de novo. |
| `make backup-database` / `backup-media` / `backup` | Backup do banco, dos arquivos enviados ou dos dois. |
| `make check-backup [file=...]` | Restaura um backup num Postgres descartável e mostra o que voltou. |
| `make restore-database file=...` | Restaura um `.sql` no banco do sistema. |
| `make create-app-role` | Cria ou atualiza o usuário do app no Postgres. |
| `make create-superuser` | Cria um superusuário e o TOTP dele. |
| `make create-totp user=...` | Cria o TOTP de um usuário pelo terminal. |
| `make protect-login [args=remove]` | Cria ou remove o desafio da Cloudflare no login. |
| `make migrations [app=...]` | Gera as migrations. |
| `make run-tests [args=...]` | Roda os testes. |
| `make django-shell` | Shell do Django. |
| `make terminal container=...` | Terminal dentro de um container. |
| `make logs [container=...]` | Acompanha os logs. |
