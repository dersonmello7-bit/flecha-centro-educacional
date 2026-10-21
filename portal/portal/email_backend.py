import json
from email.utils import parseaddr
from urllib.request import Request,urlopen
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

class DeliveryError(Exception):pass

class BrevoEmailBackend(BaseEmailBackend):
    """Entrega transacional por HTTPS; evita SMTP bloqueado no Render Free."""
    def send_messages(self,email_messages):
        sent=0
        for msg in email_messages:
            if not msg.recipients():continue
            if msg.attachments or msg.cc or msg.bcc:
                raise DeliveryError('Este canal só aceita mensagens individuais de acesso, sem anexos ou cópias.')
            name,address=parseaddr(msg.from_email)
            if not address or not settings.BREVO_API_KEY:raise DeliveryError('Configure remetente verificado e credencial de e-mail.')
            body={'sender':{'email':address,'name':name or 'Flecha'},'to':[{'email':parseaddr(value)[1]} for value in msg.to],'subject':msg.subject,'textContent':msg.body}
            request=Request('https://api.brevo.com/v3/smtp/email',data=json.dumps(body).encode('utf-8'),headers={'api-key':settings.BREVO_API_KEY,'Content-Type':'application/json','Accept':'application/json'},method='POST')
            try:
                with urlopen(request,timeout=15) as response:
                    if response.status!=201:raise DeliveryError('Entrega não confirmada.')
                    response.read(65536)
            except Exception:
                # Não replica corpo, destinatário, link de acesso ou credencial em logs.
                if not self.fail_silently:raise DeliveryError('Não foi possível entregar o e-mail. Confira a configuração do provedor.') from None
                continue
            sent+=1
        return sent
