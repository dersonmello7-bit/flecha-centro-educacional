from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.core.management.base import BaseCommand
from portal.models import AccessAttempt,Audit,PaymentProof,Document
class Command(BaseCommand):
    help='Relatório de retenção sem exclusão. Revisar finalidade, obrigação e guarda antes de apagar.'
    def handle(self,*args,**kwargs):
        cutoff=timezone.now()-timedelta(days=settings.RETENTION_DAYS)
        self.stdout.write(f'Referência para revisão: {settings.RETENTION_DAYS} dias. Não é prazo legal automático.')
        for model,field in [(AccessAttempt,'created_at'),(Audit,'created_at'),(PaymentProof,'uploaded_at'),(Document,'uploaded_at')]:
            self.stdout.write(f'{model.__name__}: {model.objects.filter(**{field+"__lt":cutoff}).count()} registros para revisão. Nenhum dado excluído.')
