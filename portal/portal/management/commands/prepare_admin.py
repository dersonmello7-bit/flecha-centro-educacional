import secrets
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.core.validators import validate_email
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from portal.models import User
class Command(BaseCommand):
    help='Prepara primeiro acesso técnico local. Não envia e-mail nem define senha compartilhada.'
    def add_arguments(self,parser):parser.add_argument('email');parser.add_argument('--activation-file',required=True)
    def handle(self,*args,**opts):
        if not settings.LOCAL:raise CommandError('Ativação em arquivo só é permitida no ambiente local.')
        validate_email(opts['email'])
        user,created=User.objects.get_or_create(email=opts['email'].strip().lower(),defaults={'role':'technical','first_name':'Administração'})
        if not created:
            self.stdout.write('Conta existente preservada. Use recuperação de acesso ou changepassword no terminal local.');return
        user.set_password(secrets.token_urlsafe(48));user.save()
        uid=urlsafe_base64_encode(force_bytes(user.pk));token=default_token_generator.make_token(user)
        target=Path(opts['activation_file']).resolve()
        # Segredos de ativação ficam fora do código e dos pacotes entregues.
        if settings.BASE_DIR not in target.parents or '.local' not in target.parts:raise CommandError('Use a pasta .local do projeto para a ativação.')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text('[InternetShortcut]\nURL='+settings.SITE_URL+f'/redefinir/{uid}/{token}/\n',encoding='utf-8')
        self.stdout.write('Primeiro acesso local preparado. O atalho de ativação expira em uma hora.')
