from urllib.parse import quote
from storages.backends.s3 import S3Storage

class PrivateS3Storage(S3Storage):
    """S3 privado. Nunca oferece URL pública ou link assinado no formulário admin."""
    default_acl=None
    file_overwrite=False
    def url(self,name,parameters=None,expire=None,http_method=None):
        return '/arquivo-armazenado/'+quote(name,safe='/')
