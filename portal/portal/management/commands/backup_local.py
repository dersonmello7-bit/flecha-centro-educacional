import sqlite3,zipfile
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.utils import timezone
class Command(BaseCommand):
    help='Backup consistente da base SQLite e arquivos privados locais. Não substitui backup de produção.'
    def handle(self,*args,**opts):
        if not settings.LOCAL or settings.DATABASES['default']['ENGINE']!='django.db.backends.sqlite3':raise CommandError('Use a política do provedor PostgreSQL em produção.')
        root=(settings.BASE_DIR/'backups').resolve();root.mkdir(exist_ok=True)
        stamp=timezone.now().strftime('%Y%m%d-%H%M%S')
        target=root/f'portal-{stamp}.sqlite3'
        with sqlite3.connect(settings.DATABASES['default']['NAME']) as source,sqlite3.connect(target) as destination:
            source.backup(destination)
            if destination.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise CommandError('Falha na verificação de integridade do backup.')
        archive=root/f'portal-{stamp}.zip'
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as out:
            out.write(target,'database.sqlite3')
            if settings.MEDIA_ROOT.exists():
                for file in settings.MEDIA_ROOT.rglob('*'):
                    if file.is_file() and not file.is_symlink():out.write(file,'private_uploads/'+file.relative_to(settings.MEDIA_ROOT).as_posix())
        self.stdout.write('Backup local criado e integridade SQLite conferida na pasta backups. Restrinja acesso e mantenha cópia criptografada fora deste computador.')
