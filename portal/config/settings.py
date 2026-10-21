import os,re
from pathlib import Path
from urllib.parse import urlparse, unquote
from django.core.exceptions import ImproperlyConfigured
BASE_DIR=Path(__file__).resolve().parent.parent
LOCAL=os.environ.get('FLECHA_LOCAL')=='1'
TESTING=os.environ.get('FLECHA_TEST')=='1'
DEBUG=LOCAL
SECRET_KEY=os.environ.get('SECRET_KEY','')
if not SECRET_KEY:
    if not (LOCAL or TESTING): raise ImproperlyConfigured('SECRET_KEY é obrigatória.')
    SECRET_KEY='apenas-testes-locais-nao-utilizar-em-producao-flecha'
ALLOWED_HOSTS=os.environ.get('ALLOWED_HOSTS','localhost,127.0.0.1,testserver' if LOCAL or TESTING else '').split(',')
if '*' in ALLOWED_HOSTS: raise ImproperlyConfigured('Não use ALLOWED_HOSTS=*')
INSTALLED_APPS=['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','portal']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware','portal.middleware.PrivateResponseMiddleware']
ROOT_URLCONF='config.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages','portal.access.navigation']}}]
WSGI_APPLICATION='config.wsgi.application'
AUTH_USER_MODEL='portal.User'
url=os.environ.get('DATABASE_URL','')
if url:
    parsed=urlparse(url)
    if parsed.scheme not in ('postgres','postgresql'): raise ImproperlyConfigured('Use PostgreSQL em produção.')
    DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':unquote(parsed.path[1:]),'USER':unquote(parsed.username or ''),'PASSWORD':unquote(parsed.password or ''),'HOST':parsed.hostname,'PORT':parsed.port or 5432,'OPTIONS':{'sslmode':'require'},'CONN_MAX_AGE':60}}
    schema=os.environ.get('DATABASE_SCHEMA','')
    if 'supabase' in (parsed.hostname or '') and not schema:raise ImproperlyConfigured('Supabase exige um schema privado dedicado, fora da API pública.')
    if schema:
        if not re.fullmatch(r'[a-z_][a-z0-9_]{0,62}',schema) or schema=='public':raise ImproperlyConfigured('Informe um nome de schema privado válido.')
        DATABASES['default']['OPTIONS']['options']='-c search_path='+schema
        DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS']=True
elif LOCAL or TESTING:
    DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'portal-local.sqlite3'}}
else: raise ImproperlyConfigured('DATABASE_URL é obrigatória em produção.')
AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
PASSWORD_HASHERS=['django.contrib.auth.hashers.PBKDF2PasswordHasher','django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher']
LANGUAGE_CODE='pt-br'
TIME_ZONE='America/Sao_Paulo'
USE_TZ=True
USE_I18N=True
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
STATIC_URL='/static/'
STATIC_ROOT=BASE_DIR/'staticfiles'
STATICFILES_DIRS=[BASE_DIR/'static']
MEDIA_ROOT=Path(os.environ.get('PRIVATE_UPLOAD_ROOT',str(BASE_DIR/'private_uploads')))
# Não há rota pública de mídia. Todo download passa por autorização.
STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}
STORAGE_ENDPOINT=os.environ.get('STORAGE_ENDPOINT','')
if STORAGE_ENDPOINT:
    if not STORAGE_ENDPOINT.startswith('https://'):raise ImproperlyConfigured('Armazenamento remoto exige HTTPS.')
    required=['STORAGE_BUCKET','STORAGE_ACCESS_KEY','STORAGE_SECRET_KEY','STORAGE_REGION']
    if not all(os.environ.get(k) for k in required):raise ImproperlyConfigured('Complete a configuração do armazenamento privado.')
    if not (LOCAL or TESTING) and os.environ.get('STORAGE_PRIVATE_VERIFIED')!='1':raise ImproperlyConfigured('Confira que o bucket é privado antes de liberar o portal.')
    STORAGES['default']={'BACKEND':'portal.storage.PrivateS3Storage','OPTIONS':{
        'endpoint_url':STORAGE_ENDPOINT,'bucket_name':os.environ['STORAGE_BUCKET'],
        'access_key':os.environ['STORAGE_ACCESS_KEY'],'secret_key':os.environ['STORAGE_SECRET_KEY'],
        'region_name':os.environ['STORAGE_REGION'],'signature_version':'s3v4','addressing_style':'path',
        'default_acl':None,'file_overwrite':False,'querystring_auth':True,
        'object_parameters':{'CacheControl':'private, no-store'},'max_memory_size':1024*1024}}
if not (LOCAL or TESTING) and not STORAGE_ENDPOINT and not os.environ.get('PRIVATE_UPLOAD_ROOT'):
    raise ImproperlyConfigured('Configure armazenamento privado persistente antes de produção.')
LOGIN_URL='login'
LOGIN_REDIRECT_URL='dashboard'
LOGOUT_REDIRECT_URL='login'
SESSION_COOKIE_AGE=3600*4
SESSION_EXPIRE_AT_BROWSER_CLOSE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Lax'
CSRF_COOKIE_HTTPONLY=True
SESSION_COOKIE_SECURE=not (LOCAL or TESTING)
CSRF_COOKIE_SECURE=not (LOCAL or TESTING)
SECURE_SSL_REDIRECT=not (LOCAL or TESTING)
SECURE_HSTS_SECONDS=31536000 if not (LOCAL or TESTING) else 0
SECURE_CONTENT_TYPE_NOSNIFF=True
X_FRAME_OPTIONS='DENY'
if os.environ.get('TRUST_RENDER_PROXY')=='1': SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
CSRF_TRUSTED_ORIGINS=[v for v in os.environ.get('CSRF_TRUSTED_ORIGINS','').split(',') if v]
DATA_UPLOAD_MAX_MEMORY_SIZE=12*1024*1024
FILE_UPLOAD_MAX_MEMORY_SIZE=1024*1024
PASSWORD_RESET_TIMEOUT=3600
EMAIL_HOST=os.environ.get('EMAIL_HOST','')
EMAIL_PORT=int(os.environ.get('EMAIL_PORT','587'))
EMAIL_USE_TLS=True
EMAIL_HOST_USER=os.environ.get('EMAIL_HOST_USER','')
EMAIL_HOST_PASSWORD=os.environ.get('EMAIL_HOST_PASSWORD','')
DEFAULT_FROM_EMAIL=os.environ.get('DEFAULT_FROM_EMAIL','')
SERVER_EMAIL=DEFAULT_FROM_EMAIL
BREVO_API_KEY=os.environ.get('BREVO_API_KEY','')
EMAIL_READY=bool((EMAIL_HOST or BREVO_API_KEY) and DEFAULT_FROM_EMAIL)
EMAIL_BACKEND='portal.email_backend.BrevoEmailBackend' if BREVO_API_KEY else ('django.core.mail.backends.smtp.EmailBackend' if EMAIL_READY else 'django.core.mail.backends.dummy.EmailBackend')
if TESTING: EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
if not (LOCAL or TESTING) and not EMAIL_READY: raise ImproperlyConfigured('Configure envio de e-mail antes de ativar o portal.')
RETENTION_DAYS=int(os.environ.get('RETENTION_DAYS','365'))
SITE_URL=os.environ.get('SITE_URL','http://127.0.0.1:8800' if LOCAL or TESTING else '')
if not (LOCAL or TESTING) and not SITE_URL.startswith('https://'): raise ImproperlyConfigured('SITE_URL deve usar HTTPS.')
