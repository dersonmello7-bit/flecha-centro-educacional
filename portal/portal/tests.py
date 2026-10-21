import tempfile,re
from datetime import date,timedelta
from pathlib import Path
from django.test import TestCase,Client,override_settings
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils import timezone
from .models import *
from .validators import validate_file
from .access import students_for

class IsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a=User.objects.create_user('familia-a@example.invalid','SenhaFicticia12345!',first_name='Família A')
        cls.b=User.objects.create_user('familia-b@example.invalid','SenhaFicticia12345!')
        cls.t=User.objects.create_user('prof@example.invalid','SenhaFicticia12345!',role='teacher')
        cls.f=User.objects.create_user('finance@example.invalid','SenhaFicticia12345!',role='finance')
        cls.p=User.objects.create_user('ped@example.invalid','SenhaFicticia12345!',role='pedagogy')
        cls.tech=User.objects.create_user('tech@example.invalid','SenhaFicticia12345!',role='technical')
        cls.c=Classroom.objects.create(name='Turma fictícia A',stage='nursery');cls.c.staff.add(cls.t)
        cls.d=Classroom.objects.create(name='Turma fictícia B',stage='year1')
        cls.sa=Student.objects.create(name='Aluno fictício A',classroom=cls.c,period='Integral')
        cls.sa2=Student.objects.create(name='Aluno fictício A2',classroom=cls.c,period='Parcial')
        cls.sb=Student.objects.create(name='Aluno fictício B',classroom=cls.d,period='Parcial')
        for student in (cls.sa,cls.sa2):GuardianLink.objects.create(guardian=cls.a,student=student,can_finance=True,verified_at=timezone.now())
        GuardianLink.objects.create(guardian=cls.b,student=cls.sb,verified_at=timezone.now())
        cls.inv=Invoice.objects.create(student=cls.sa,competence=date(2026,10,1),due_date=date(2026,10,10),amount='100.00')
        cls.inv_b=Invoice.objects.create(student=cls.sb,competence=date(2026,10,1),due_date=date(2026,10,10),amount='999.00')
        cls.n=Notice.objects.create(title='Comunicado turma A',content='Texto fictício',classroom=cls.c,author=cls.p,published=True,published_at=timezone.now(),require_read=True)
        cls.nb=Notice.objects.create(title='Exclusivo turma B',content='Reservado',classroom=cls.d,author=cls.p,published=True,published_at=timezone.now())
        cls.future=Notice.objects.create(title='Publicação futura',content='Reservado',author=cls.p,published=True,published_at=timezone.now()+timedelta(days=5))
    def setUp(self):self.client.force_login(self.a)
    def test_anonymous_all_routes_require_auth(self):
        self.client.logout()
        for path in ('/','/comunicados/','/calendario/','/cardapio/','/financeiro/','/documentos/','/atendimento/',f'/agenda/{self.sa.pk}/',f'/arquivo/document/1/'):
            self.assertEqual(self.client.get(path).status_code,302,path)
    def test_multiple_children_and_tampered_selection(self):
        response=self.client.get('/');self.assertContains(response,self.sa.name);self.assertContains(response,self.sa2.name);self.assertNotContains(response,self.sb.name)
        self.assertEqual(self.client.get('/',{'aluno':self.sb.pk}).status_code,404)
        self.assertEqual(self.client.get('/',{'aluno':self.sa2.pk}).status_code,200)
    def test_single_child(self):
        self.client.force_login(self.b);response=self.client.get('/');self.assertEqual(len(response.context['students']),1);self.assertContains(response,self.sb.name)
    def test_no_link_is_empty_including_general_notice(self):
        user=User.objects.create_user('semvinculo@example.invalid','PasswordFake123!');self.client.force_login(user)
        Notice.objects.create(title='Geral reservado',content='...',author=self.p,published=True,published_at=timezone.now())
        self.assertNotContains(self.client.get('/comunicados/'),'Geral reservado');self.assertContains(self.client.get('/'),'precisa ser liberado')
    def test_inactive_or_unverified_link_denied(self):
        GuardianLink.objects.filter(guardian=self.a).update(active=False)
        self.assertEqual(self.client.get(f'/agenda/{self.sa.pk}/').status_code,404)
        GuardianLink.objects.filter(guardian=self.a).update(active=True,verified_at=None)
        self.assertEqual(self.client.get(f'/agenda/{self.sa.pk}/').status_code,404)
    def test_notice_scope_and_future(self):
        r=self.client.get('/comunicados/');self.assertContains(r,self.n.title);self.assertNotContains(r,self.nb.title);self.assertNotContains(r,self.future.title)
    def test_read_confirmation_post_only_idempotent(self):
        url=f'/comunicados/{self.n.pk}/leitura/'
        self.assertEqual(self.client.get(url).status_code,405)
        for _ in range(2):self.assertEqual(self.client.post(url).status_code,302)
        self.assertEqual(ReadConfirmation.objects.filter(user=self.a,notice=self.n).count(),1)
        self.assertEqual(self.client.post(f'/comunicados/{self.nb.pk}/leitura/').status_code,404)
    def test_agenda_idor_and_post(self):
        self.assertEqual(self.client.get(f'/agenda/{self.sb.pk}/').status_code,404)
        self.assertEqual(self.client.post(f'/agenda/{self.sb.pk}/',{'text':'acesso indevido'}).status_code,404)
        self.assertEqual(self.client.post(f'/agenda/{self.sa.pk}/',{'text':'Recado fictício'}).status_code,302)
        self.assertEqual(FamilyMessage.objects.get().author,self.a)
    def test_age_specific_agenda(self):
        item=Agenda(student=self.sb,date=date.today(),food='Não habilitado',author=self.p)
        with self.assertRaises(ValidationError):item.full_clean()
        item=Agenda(student=self.sa,date=date.today(),food='Boa aceitação',author=self.t);item.full_clean();item.save()
        self.assertContains(self.client.get(f'/agenda/{self.sa.pk}/'),'Boa aceitação')
    def test_classroom_configuration_validated(self):
        self.c.agenda_fields=['sensitive_arbitrary']
        with self.assertRaises(ValidationError):self.c.full_clean()
    def test_finance_permission_and_idor(self):
        response=self.client.get('/financeiro/');self.assertContains(response,'100,00');self.assertNotContains(response,'999,00')
        self.assertEqual(self.client.get(f'/financeiro/{self.inv_b.pk}/comprovante/').status_code,404)
        GuardianLink.objects.filter(guardian=self.a).update(can_finance=False)
        self.assertNotContains(self.client.get('/financeiro/'),'100,00');self.assertEqual(self.client.get(f'/financeiro/{self.inv.pk}/comprovante/').status_code,404)
    def test_proof_cannot_mark_paid_or_approved(self):
        with override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.InMemoryStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}):
            r=self.client.post(f'/financeiro/{self.inv.pk}/comprovante/',{'file':SimpleUploadedFile('recibo.pdf',b'%PDF-1.4\nfictional test\n%%EOF'),'approved':'true','status':'reviewed'})
            self.assertEqual(r.status_code,302)
            obj=PaymentProof.objects.get();self.assertFalse(obj.approved);self.assertEqual(obj.status,'pending')
            self.inv.refresh_from_db();self.assertEqual(self.inv.status,'open')
            self.assertEqual(self.client.get(f'/arquivo/proof/{obj.pk}/').status_code,404)
    def test_document_scope_quarantine_and_private_url(self):
        with override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.InMemoryStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}):
            own=Document.objects.create(title='Individual A',student=self.sa,file=SimpleUploadedFile('a.pdf',b'%PDF-1.4\n%%EOF'),uploaded_by=self.p,published=True,approved=True)
            other=Document.objects.create(title='Individual B',student=self.sb,file=SimpleUploadedFile('b.pdf',b'%PDF-1.4\n%%EOF'),uploaded_by=self.p,published=True,approved=True)
            self.assertEqual(self.client.get(f'/arquivo/document/{own.pk}/').status_code,200)
            self.assertEqual(self.client.get(f'/arquivo/document/{other.pk}/').status_code,404)
            own.approved=False;own.save();self.assertEqual(self.client.get(f'/arquivo/document/{own.pk}/').status_code,404)
            self.assertEqual(self.client.get('/'+own.file.name).status_code,404)
    def test_finance_only_document_denied(self):
        obj=Document.objects.create(title='Financeiro reservado',student=self.sb,finance_only=True,file='none.pdf',uploaded_by=self.f,published=True,approved=True)
        self.client.force_login(self.b);self.assertNotContains(self.client.get('/documentos/'),obj.title)
    def test_malicious_uploads_rejected(self):
        for name,data in [('script.html',b'<script>'),('fake.pdf',b'not PDF'),('active.pdf',b'%PDF-1.4 /JavaScript evil %%EOF'),('fake.png',b'not image')]:
            with self.assertRaises(ValidationError):validate_file(SimpleUploadedFile(name,data))
    def test_confirmed_payment_requires_reconciliation(self):
        self.inv.status='paid'
        with self.assertRaises(ValidationError):self.inv.full_clean()
    def test_ticket_private_and_protocol(self):
        self.client.post(f'/atendimento/novo/{self.sa.pk}/',{'category':'administrative','subject':'Pedido fictício','content':'Preciso de orientação.'})
        ticket=Ticket.objects.get();self.assertTrue(ticket.protocol.startswith('FLE-'))
        self.client.force_login(self.b);self.assertEqual(self.client.get(f'/atendimento/{ticket.pk}/').status_code,404)
    def test_finance_ticket_category_server_checked(self):
        self.client.force_login(self.b)
        r=self.client.post(f'/atendimento/novo/{self.sb.pk}/',{'category':'finance','subject':'Tentativa','content':'...'})
        self.assertEqual(r.status_code,200);self.assertFalse(Ticket.objects.exists())
    def test_teacher_cannot_access_other_class_or_finance(self):
        self.client.force_login(self.t)
        self.assertEqual(self.client.get(f'/agenda/{self.sb.pk}/').status_code,404)
        self.assertEqual(self.client.get('/administracao/portal/invoice/').status_code,403)
        self.assertEqual(self.client.get(f'/administracao/portal/student/{self.sb.pk}/change/').status_code,403)
        self.assertEqual(self.client.get('/administracao/portal/user/').status_code,403)
    def test_teacher_cannot_publish_general_or_foreign_class(self):
        self.client.force_login(self.t)
        r=self.client.get('/administracao/portal/notice/add/');self.assertEqual(r.status_code,200)
        field=r.context['adminform'].form.fields['classroom'];self.assertTrue(field.required);self.assertNotIn(self.d,list(field.queryset))
    def test_finance_cannot_read_agenda_and_technical_cannot_read_school(self):
        self.client.force_login(self.f);self.assertEqual(self.client.get(f'/agenda/{self.sa.pk}/').status_code,404)
        self.client.force_login(self.tech)
        for model in ('student','agenda','invoice','document','ticket'):
            self.assertEqual(self.client.get(f'/administracao/portal/{model}/').status_code,403,model)
    def test_sensitive_admin_file_review_gated(self):
        self.client.force_login(self.tech);self.assertEqual(self.client.get('/conferencia-arquivo/proof/1/').status_code,404)
        self.client.force_login(self.t);self.assertEqual(self.client.get('/conferencia-arquivo/document/1/').status_code,404)
    def test_csrf_rejects_mutation(self):
        c=Client(enforce_csrf_checks=True);c.force_login(self.a)
        self.assertEqual(c.post(f'/comunicados/{self.n.pk}/leitura/').status_code,403)
    def test_xss_is_escaped(self):
        self.n.content='<script>alert(1)</script>';self.n.save()
        r=self.client.get('/comunicados/');self.assertNotContains(r,'<script>alert(1)</script>');self.assertContains(r,'&lt;script&gt;')
    def test_password_reset_non_enumerating(self):
        self.client.logout();url='/recuperar/'
        self.assertEqual(self.client.post(url,{'email':self.a.email}).status_code,302)
        self.assertEqual(self.client.post(url,{'email':'inexistente@example.invalid'}).status_code,302)
        self.assertEqual(len(mail.outbox),1)
    def test_reset_token_one_time(self):
        token=default_token_generator.make_token(self.a);uid=urlsafe_base64_encode(force_bytes(self.a.pk));self.client.logout()
        self.assertTrue(default_token_generator.check_token(self.a,token))
        self.client.get(f'/redefinir/{uid}/{token}/')
        r=self.client.post(f'/redefinir/{uid}/set-password/',{'new_password1':'SenhaNovaFicticia321!','new_password2':'SenhaNovaFicticia321!'})
        self.assertEqual(r.status_code,302);self.a.refresh_from_db();self.assertFalse(default_token_generator.check_token(self.a,token));self.assertTrue(self.a.check_password('SenhaNovaFicticia321!'))
    def test_rate_limit_and_open_redirect(self):
        self.client.logout()
        for _ in range(5):self.client.post('/entrar/',{'username':self.a.email,'password':'incorrect'})
        self.assertEqual(self.client.post('/entrar/',{'username':self.a.email,'password':'incorrect'}).status_code,429)
        AccessAttempt.objects.all().delete()
        r=self.client.post('/entrar/',{'username':self.a.email,'password':'SenhaFicticia12345!','next':'https://malicious.invalid/'})
        self.assertEqual(r.status_code,302);self.assertEqual(r.url,'/')
    def test_calendar_and_menu_visibility(self):
        Event.objects.create(title='Reunião fictícia',content='...',author=self.p,classroom=self.c,published=True,published_at=timezone.now(),date=timezone.localdate(),category='meeting')
        Menu.objects.create(title='Cardápio fictício',content='Arroz e feijão',author=self.p,classroom=self.c,published=True,published_at=timezone.now(),week=timezone.localdate(),reviewed_by='Equipe fictícia')
        self.assertContains(self.client.get('/calendario/',{'modo':'mes'}),'Reunião fictícia');self.assertContains(self.client.get('/cardapio/'),'Cardápio fictício')
        self.client.force_login(self.b);self.assertNotContains(self.client.get('/calendario/'),'Reunião fictícia');self.assertNotContains(self.client.get('/cardapio/'),'Cardápio fictício')
    def test_response_headers_and_logout_post_only(self):
        r=self.client.get('/');self.assertIn('no-store',r['Cache-Control']);self.assertEqual(r['X-Frame-Options'],'DENY');self.assertIn("default-src 'self'",r['Content-Security-Policy'])
        self.assertEqual(self.client.get('/sair/').status_code,405);self.assertEqual(self.client.post('/sair/').status_code,302)
    def test_invalid_student_selector_is_not_server_error(self):
        for value in ['abc','-1','9'*100,'١٢']:
            self.assertEqual(self.client.get('/',{'aluno':value}).status_code,404)
    def test_login_email_case_and_password_hash(self):
        self.client.logout();r=self.client.post('/entrar/',{'username':self.a.email.upper(),'password':'SenhaFicticia12345!'})
        self.assertEqual(r.status_code,302);self.assertNotEqual(self.a.password,'SenhaFicticia12345!');self.assertTrue(self.a.password.startswith('pbkdf2_'))
    def test_school_only_and_financial_only_links(self):
        GuardianLink.objects.filter(guardian=self.a).update(can_school=False,can_finance=True)
        self.assertEqual(self.client.get(f'/agenda/{self.sa.pk}/').status_code,404)
        self.assertContains(self.client.get('/financeiro/'),'100,00')
        self.assertEqual(self.client.get('/').status_code,200)
    def test_admin_creates_account_without_shared_password(self):
        self.client.force_login(self.tech)
        r=self.client.post('/administracao/portal/user/add/',{'email':'nova.familia@example.invalid','first_name':'Nova','last_name':'Família','role':'guardian','_save':'Salvar'})
        self.assertEqual(r.status_code,302)
        user=User.objects.get(email='nova.familia@example.invalid');self.assertTrue(user.has_usable_password());self.assertFalse(user.is_staff)
        self.assertFalse(GuardianLink.objects.filter(guardian=user).exists())
    def test_direction_cannot_promote_account(self):
        direction=User.objects.create_user('direction@example.invalid','DirecaoFicticia123!',role='direction');self.client.force_login(direction)
        r=self.client.post('/administracao/portal/user/add/',{'email':'escalation@example.invalid','first_name':'x','role':'technical','_save':'Salvar'})
        self.assertEqual(r.status_code,200);self.assertFalse(User.objects.filter(email='escalation@example.invalid').exists())
    def test_teacher_registers_scoped_agenda(self):
        self.client.force_login(self.t)
        r=self.client.post('/administracao/portal/agenda/add/',{'student':self.sa.pk,'date':'2026-10-20','activities':'Atividade fictícia','food':'Exemplo','rest':'','pedagogy':'','school_note':'','_save':'Salvar'})
        self.assertEqual(r.status_code,302);self.assertEqual(Agenda.objects.get().author,self.t)
        r=self.client.post('/administracao/portal/agenda/add/',{'student':self.sb.pk,'date':'2026-10-20','activities':'Tentativa','_save':'Salvar'})
        self.assertEqual(r.status_code,200);self.assertEqual(Agenda.objects.count(),1)
    def test_storage_path_still_authorizes_download(self):
        with override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.InMemoryStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}):
            item=Document.objects.create(title='Armazenamento privado',student=self.sa,file=SimpleUploadedFile('doc.pdf',b'%PDF-1.4\n%%EOF'),uploaded_by=self.p,published=True,approved=True)
            url='/arquivo-armazenado/'+item.file.name
            self.assertEqual(self.client.get(url).status_code,200)
            self.client.force_login(self.b);self.assertEqual(self.client.get(url).status_code,404)
            self.client.logout();self.assertEqual(self.client.get(url).status_code,302)
    def test_https_email_backend_does_not_expose_recovery_token_in_error(self):
        from .email_backend import BrevoEmailBackend,DeliveryError
        from django.core.mail import EmailMessage
        from unittest.mock import patch,MagicMock
        msg=EmailMessage('Acesso fictício','token-ficticio-nao-logar','Escola <escola@example.invalid>',['destino@example.invalid'])
        with override_settings(BREVO_API_KEY='chave-ficticia-nao-logar'):
            with patch('portal.email_backend.urlopen') as call:
                call.return_value.__enter__.return_value.status=201
                self.assertEqual(BrevoEmailBackend().send_messages([msg]),1)
                req=call.call_args[0][0];self.assertTrue(req.full_url.startswith('https://api.brevo.com/'));self.assertEqual(req.method,'POST')
            with patch('portal.email_backend.urlopen',side_effect=RuntimeError('segredo-nao-expor')):
                with self.assertRaises(DeliveryError) as raised:BrevoEmailBackend().send_messages([msg])
                self.assertNotIn('segredo-nao-expor',str(raised.exception));self.assertNotIn('token-ficticio',str(raised.exception))
    def test_bootstrap_admin_is_idempotent_without_fixed_password(self):
        from django.core.management import call_command
        from unittest.mock import patch
        import os
        with override_settings(EMAIL_READY=True,DEFAULT_FROM_EMAIL='escola@example.invalid'),patch.dict(os.environ,{'BOOTSTRAP_ADMIN_EMAIL':'admin-ficticio@example.invalid'}):
            call_command('bootstrap_admin');call_command('bootstrap_admin')
        user=User.objects.get(email='admin-ficticio@example.invalid')
        self.assertEqual(user.role,'technical');self.assertFalse(user.is_superuser);self.assertEqual(Audit.objects.filter(actor=user,action='bootstrap.invited').count(),1)
        self.assertEqual(len(mail.outbox),1)
    def test_health_exposes_no_database_details(self):
        self.client.logout();r=self.client.get('/health/');self.assertEqual(r.json(),{'status':'ok'})
    def test_s3_never_generates_public_or_presigned_file_url(self):
        from .storage import PrivateS3Storage
        storage=PrivateS3Storage(bucket_name='ficticio-privado',access_key='chave-ficticia',secret_key='segredo-ficticio',endpoint_url='https://storage.example.invalid',region_name='test')
        url=storage.url('quarantine/exemplo.pdf')
        self.assertEqual(url,'/arquivo-armazenado/quarantine/exemplo.pdf');self.assertNotIn('https://',url);self.assertNotIn('Signature',url)
