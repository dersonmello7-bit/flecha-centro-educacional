import secrets
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Verifica gravação/leitura privada com um arquivo sintético e remove a própria amostra.'

    def handle(self, *args, **options):
        if not settings.STORAGE_ENDPOINT:
            raise CommandError('Configure o armazenamento remoto privado antes da verificação.')
        payload = b'%PDF-1.4\n% Flecha storage connectivity check. No personal data.\n%%EOF\n'
        name = None
        try:
            name = default_storage.save('operational-check/' + secrets.token_hex(16) + '.pdf', ContentFile(payload))
            with default_storage.open(name, 'rb') as file:
                if file.read() != payload:
                    raise ValueError('Conteúdo diferente.')
            if default_storage.size(name) != len(payload):
                raise ValueError('Tamanho diferente.')
        except Exception:
            raise CommandError('A gravação/leitura do armazenamento privado não foi confirmada.') from None
        finally:
            if name:
                try:
                    default_storage.delete(name)
                except Exception:
                    raise CommandError('Confira a remoção da amostra sintética de armazenamento.') from None
        self.stdout.write('Armazenamento privado: gravação, leitura e remoção da amostra confirmadas.')
