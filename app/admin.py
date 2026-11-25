import unicodedata
from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone
from reversion.admin import VersionAdmin
import reversion
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group as BaseGroup
from .models import User, Group
from .utils.permissions_report import permissions_report_pdf, user_permissions_report


def without_accents(text):
    # O unaccent do banco tira o acento da coluna; o termo digitado chega como
    # veio. Sem limpar os dois lados, procurar "José" deixaria de encontrar o
    # próprio "José".
    return ''.join(
        letter for letter in unicodedata.normalize('NFD', text)
        if not unicodedata.combining(letter)
    )


class UnaccentSearchAdmin(admin.ModelAdmin):
    """Busca que ignora acento, nos campos marcados com __unaccent."""

    def get_search_results(self, request, queryset, search_term):
        return super().get_search_results(request, queryset, without_accents(search_term))


# User Admin
# Registrado antes do VersionAdmin, que senão registraria todos os campos: o
# histórico guardaria o hash da senha, e reverter devolveria a senha antiga.
reversion.register(User, exclude=('password', 'last_login'))
@admin.register(User)
class UserAdmin(VersionAdmin, UnaccentSearchAdmin, BaseUserAdmin):
    list_display = ('username', 'first_name', 'last_name', 'email', 'last_login', 'is_staff', 'is_superuser', 'is_active',)
    search_fields = ('username', 'email', 'first_name__unaccent', 'last_name__unaccent', 'observations__unaccent',)
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups',)
    filter_horizontal = ('groups', 'user_permissions',)
    model = User
    ordering = ('username',)
    actions = ('deactivate_users', 'permissions_report',)
    fieldsets = (
        (None, {
            'fields': ('username', 'password',)
        }),
        ('Informações pessoais', {
            'fields': ('first_name', 'last_name', 'email',)
        }),
        ('Permissões', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions',)
        }),
        ('Datas importantes', {
            'fields': ('last_login', 'date_joined',)
        }),
        ('Observações', {
            'fields': ('observations',)
        }),
    )
    add_fieldsets = (
        (None, {
            'fields': ('username', 'password1', 'password2',),
        }),
    )

    @admin.action(description='Desativar usuários selecionados')
    def deactivate_users(self, request, queryset):
        updated = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f'{updated} usuário(s) desativado(s) com sucesso.', messages.SUCCESS)

    @admin.action(description='Gerar relatório de permissões dos usuários selecionados')
    def permissions_report(self, request, queryset):
        pdf = permissions_report_pdf(
            user_permissions_report(queryset),
            request.user.get_full_name() or request.user.username,
        )
        file_name = f'relatorio-permissoes-{timezone.localtime():%Y%m%d-%H%M}.pdf'
        return HttpResponse(pdf, content_type='application/pdf', headers={
            'Content-Disposition': f'attachment; filename="{file_name}"',
        })


# Group Admin
reversion.register(BaseGroup)
reversion.register(Group)
admin.site.unregister(BaseGroup)
@admin.register(Group)
class GroupAdmin(VersionAdmin, UnaccentSearchAdmin, BaseGroupAdmin):
    search_fields = ('name__unaccent',)
