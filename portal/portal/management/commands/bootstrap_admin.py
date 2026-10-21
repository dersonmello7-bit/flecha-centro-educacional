import os,secrets
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from portal.models import User,Audit
class Command(BaseCommand):
    help='Prepara administrador técnico e envia um único convite de ativação por canal configurado.'
    def handle(self,*args,**opts):
        email=os.environ.get('BOOTSTRAP_ADMIN_EMAIL','').strip().lower()
        if not email or not settings.EMAIL_READY:raise CommandError('Configure endereço administrativo e entrega de e-mails.')
        validate_email(email)
        user,created=User.objects.get_or_create(email=email,defaults={'role':'technical','first_name':'Administração'})
        if user.role not in ('technical','general_admin'):raise CommandError('Conta existente possui outro perfil; confira manualmente.')
        if created:user.set_password(secrets.token_urlsafe(48));user.save()
        if Audit.objects.filter(actor=user,action='bootstrap.invited').exists():return
        uid=urlsafe_base64_encode(force_bytes(user.pk));token=default_token_generator.make_token(user)
        body='Defina sua senha individual da Área da Família Flecha neste link temporário:\n'+settings.SITE_URL+f'/redefinir/{uid}/{token}/\n\nO link expira em uma hora. Não o compartilhe.'
        try:result=EmailMessage('Flecha — primeiro acesso administrativo',body,settings.DEFAULT_FROM_EMAIL,[email]).send()
        except Exception:raise CommandError('A entrega do convite não foi confirmada. Verifique o provedor de e-mail.') from None
        if result!=1:raise CommandError('Convite não enviado.')
        Audit.objects.create(actor=user,action='bootstrap.invited')
        self.stdout.write('Administrador preparado e convite enviado, sem senha compartilhada.')
