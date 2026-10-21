"""Início de um único serviço gratuito; nunca carrega demonstração."""
import os,subprocess,sys
def main():
    if os.environ.get('FLECHA_LOCAL')=='1' or os.environ.get('FLECHA_TEST')=='1':raise SystemExit('Modo local/teste não deve ser publicado.')
    subprocess.run([sys.executable,'manage.py','migrate','--noinput'],check=True)
    if os.environ.get('BOOTSTRAP_ADMIN_EMAIL'):subprocess.run([sys.executable,'manage.py','bootstrap_admin'],check=True)
    port=os.environ.get('PORT','10000')
    if not port.isdigit():raise SystemExit('PORT inválida.')
    os.execvp('gunicorn',['gunicorn','config.wsgi:application','--bind',f'0.0.0.0:{port}','--workers','1','--threads','2','--timeout','90'])
if __name__=='__main__':main()
