from pathlib import Path
from uuid import uuid4
from django.core.exceptions import ValidationError
from PIL import Image
MAX_UPLOAD=10*1024*1024
def private_path(instance,name):
    return f'quarantine/{uuid4().hex}{Path(name).suffix.lower()}'
def validate_file(file):
    if file.size>MAX_UPLOAD: raise ValidationError('Arquivo maior que 10 MB.')
    ext=Path(file.name).suffix.lower()
    if ext not in ('.pdf','.jpg','.jpeg','.png'): raise ValidationError('Use PDF, JPG ou PNG.')
    file.seek(0)
    if ext=='.pdf':
        data=file.read()
        if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-1024:]: raise ValidationError('PDF inválido.')
        if any(token in data.lower() for token in (b'/javascript',b'/openaction',b'/embeddedfile',b'/launch',b'/js ')):
            raise ValidationError('PDF com conteúdo ativo não permitido.')
    else:
        try:
            img=Image.open(file)
            if img.width*img.height>25000000 or img.format not in ('PNG','JPEG'): raise ValueError()
            img.verify()
        except Exception as exc: raise ValidationError('Imagem inválida ou muito grande.') from exc
    file.seek(0)
