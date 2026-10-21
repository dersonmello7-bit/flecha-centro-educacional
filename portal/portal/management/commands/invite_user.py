from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth.forms import PasswordResetForm
from django.http import HttpRequest
from urllib.parse import urlparse
from portal.models import User
class Command(BaseCommand):
    help='Envia convite individual para conta cadastrada. Requer SMTP configurado.'
    def add_arguments(self,p):p.add_argument('email')
    def handle(self,*args,**opts):
        if not settings.EMAIL_READY:raise CommandError('Configure SMTP antes de enviar convites. Nenhuma mensagem foi enviada.')
        user=User.objects.filter(email__iexact=opts['email'],is_active=True).first()
        if not user:raise CommandError('Cadastre e confira a conta antes de convidar.')
        if user.role=='guardian' and not user.guardianlink_set.filter(active=True,verified_at__isnull=False).exists():raise CommandError('Confira o vínculo com o aluno antes de convidar.')
        if not user.has_usable_password():raise CommandError('Use uma senha aleatória não divulgada ao criar a conta para permitir ativação por e-mail.')
        form=PasswordResetForm({'email':user.email});form.is_valid()
        form.save(domain_override=urlparse(settings.SITE_URL).netloc,use_https=settings.SITE_URL.startswith('https://'),from_email=settings.DEFAULT_FROM_EMAIL,email_template_name='registration/password_reset_email.txt',subject_template_name='registration/password_reset_subject.txt')
        self.stdout.write('Convite enviado ao endereço cadastrado. O link é individual e temporário.')
