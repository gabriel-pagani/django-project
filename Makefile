MAKEFLAGS += --no-print-directory

COMPOSE = docker compose -f deploy/docker-compose.yml

# Na primeira subida ainda não há banco para copiar: make build-system backup=no.
backup ?= yes

# As tags das imagens (postgres:18, python:3.12-slim-trixie...) recebem as
# correções de segurança sem mudar de nome. Sem o pull, o build reaproveita a
# imagem que já está na máquina, e o Dependabot não avisa porque a tag é a mesma.
#
# O nginx guarda o IP do django e só lê o http.conf ao subir: sem recriá-lo, ele
# continua apontando para o container antigo e com a configuração antiga.
build-system:
	@$(MAKE) maybe-backup-system \
		&& $(COMPOSE) pull --ignore-buildable \
		&& $(COMPOSE) build --pull \
		&& $(COMPOSE) up -d \
		&& $(COMPOSE) up -d --force-recreate nginx

start-system:
	@$(COMPOSE) up -d

stop-system:
	@$(COMPOSE) down

restart-system:
	@$(COMPOSE) down && $(COMPOSE) up -d

# O volume novo do Postgres nasce só com o superusuário: o usuário do app é
# criado antes de o django subir.
reset-system:
	@$(MAKE) maybe-backup-system \
		&& $(COMPOSE) down -v \
		&& $(COMPOSE) up -d --wait postgres \
		&& $(MAKE) create-app-role \
		&& $(MAKE) build-system backup=no

reset-system-cache:
	@$(COMPOSE) exec redis redis-cli FLUSHDB

# Os backups só podem ser lidos pelo dono: o dump tem os hashes das senhas.
backup-database:
	@umask 077; mkdir -p backups; FILE="backups/$$(date +%Y%m%d-%H%M%S).sql"; \
	$(COMPOSE) exec -T postgres sh -c 'pg_dump -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" --no-owner --no-privileges' > "$$FILE.tmp" \
		&& mv "$$FILE.tmp" "$$FILE" || { rm -f "$$FILE.tmp"; exit 1; }

backup-media:
	@umask 077; mkdir -p backups; FILE="backups/media-$$(date +%Y%m%d-%H%M%S).tar.gz"; \
	$(COMPOSE) exec -T django sh -c 'tar czf - -C /app/media_root .' > "$$FILE.tmp" \
		&& mv "$$FILE.tmp" "$$FILE" || { rm -f "$$FILE.tmp"; exit 1; }

backup-system:
	@$(MAKE) backup-database && $(MAKE) backup-media

maybe-backup-system:
	@case "$(backup)" in \
		yes|true|on|1) $(MAKE) backup-system ;; \
		no|false|off|0) echo "backup=$(backup): pulando o backup" ;; \
		*) echo "backup=$(backup): use yes ou no" >&2; exit 1 ;; \
	esac

# Restaura o backup num Postgres descartável, sem rede e sem tocar no banco do
# sistema, e mostra o que voltou. Sem file=, usa o .sql mais recente de backups/.
check-backup:
	@FILE="$${file:-$$(ls -t backups/2*.sql 2>/dev/null | head -1)}"; \
	[ -s "$$FILE" ] || { echo "nenhum backup .sql em $(CURDIR)/backups (use file=...)" >&2; exit 1; }; \
	NAME="check-backup-$$$$"; \
	docker run -d --rm --name "$$NAME" --network none -e POSTGRES_PASSWORD=check postgres:18 >/dev/null || exit 1; \
	trap 'docker stop "$$NAME" >/dev/null' EXIT; \
	until docker exec "$$NAME" pg_isready -q -h 127.0.0.1 -U postgres; do sleep 1; done; \
	docker exec -i "$$NAME" psql -q -v ON_ERROR_STOP=1 -U postgres -d postgres < "$$FILE" >/dev/null \
		|| { echo "falha ao restaurar $$FILE" >&2; exit 1; }; \
	echo "$$FILE restaurado:"; \
	docker exec "$$NAME" psql -U postgres -d postgres -c "SELECT \
		(SELECT count(*) FROM app_user) AS usuarios, \
		(SELECT max(applied) FROM django_migrations) AS ultima_migration"
	@MEDIA="$$(ls -t backups/media-*.tar.gz 2>/dev/null | head -1)"; \
	[ -z "$$MEDIA" ] || [ -n "$(file)" ] || { tar tzf "$$MEDIA" >/dev/null && echo "$$MEDIA íntegro: $$(tar tzf "$$MEDIA" | grep -vc '/$$') arquivos"; }

# Num banco vazio. O dump volta com as tabelas do superusuário: rode
# make create-app-role em seguida para o app voltar a ser o dono.
restore-database:
	@test -n "$(file)" || { echo "use: make restore-database file=backups/....sql" >&2; exit 1; }
	@$(COMPOSE) exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' < "$(file)"

create-app-role:
	@$(COMPOSE) run --rm --no-deps -T -v "$(PWD)/scripts:/app/scripts" tools python scripts/create_app_role.py

# Desafio da Cloudflare nas telas de entrada; args=remove desfaz.
protect-login:
	@$(COMPOSE) run --rm --no-deps -T -v "$(PWD)/scripts:/app/scripts" tools python scripts/cloudflare_login_rule.py $(args)

make-migrations:
	@$(COMPOSE) run --rm --no-deps -v "$(PWD)/app:/app/app" django python manage.py makemigrations $(app)

# Depois que o requirements.txt muda: $(COMPOSE) build tests
run-tests:
	@$(COMPOSE) run --rm tests python -m pytest -vv $(args)

create-superuser:
	@$(COMPOSE) exec django python manage.py createsuperuser
	@$(COMPOSE) exec -T django python manage.py shell < scripts/create_totp.py

create-totp:
	@$(COMPOSE) exec -T -e TOTP_USER="$(user)" django python manage.py shell < scripts/create_totp.py

container-terminal:
	@$(COMPOSE) exec $(container) sh

containers-logs:
	@$(COMPOSE) logs -f $(container)

django-shell:
	@$(COMPOSE) exec django python manage.py shell
