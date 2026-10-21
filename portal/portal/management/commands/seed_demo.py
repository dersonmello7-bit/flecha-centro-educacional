from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.utils import timezone
from portal.models import *
class Command(BaseCommand):
    help='Cria exclusivamente registros fictícios para avaliação local; recusa produção.'
    def handle(self,*args,**kwargs):
        if not settings.LOCAL:raise CommandError('Dados demonstrativos só são permitidos localmente.')
        today=timezone.localdate()
        defs=[('familia.exemplo@example.invalid','ExemploFamilia#2026!','guardian','Família Exemplo'),('outra.familia@example.invalid','OutraFamilia#2026!','guardian','Outra Família'),('direcao.exemplo@example.invalid','DirecaoExemplo#2026!','direction','Direção Exemplo'),('professor.exemplo@example.invalid','ProfessorExemplo#2026!','teacher','Professor Exemplo'),('financeiro.exemplo@example.invalid','FinanceiroExemplo#2026!','finance','Financeiro Exemplo')]
        users={}
        for email,password,role,name in defs:
            u,created=User.objects.get_or_create(email=email,defaults={'role':role,'first_name':name})
            if created:u.set_password(password);u.save()
            users[role if role!='guardian' else email]=u
        classroom,_=Classroom.objects.get_or_create(external_id='DEMO-TURMA-A',defaults={'name':'Turma Descobertas · fictícia','stage':'nursery'})
        classroom.staff.add(users['teacher'])
        other_class,_=Classroom.objects.get_or_create(external_id='DEMO-TURMA-B',defaults={'name':'1º Ano · fictício','stage':'year1'})
        a,_=Student.objects.get_or_create(external_id='DEMO-ALUNO-A',defaults={'name':'Criança Exemplo A','classroom':classroom,'period':'Integral'})
        a2,_=Student.objects.get_or_create(external_id='DEMO-ALUNO-A2',defaults={'name':'Criança Exemplo A2','classroom':other_class,'period':'Parcial — manhã'})
        b,_=Student.objects.get_or_create(external_id='DEMO-ALUNO-B',defaults={'name':'Criança Exemplo B','classroom':other_class,'period':'Parcial — tarde'})
        family=users['familia.exemplo@example.invalid']
        for student in (a,a2):GuardianLink.objects.get_or_create(guardian=family,student=student,defaults={'can_finance':True,'verified_at':timezone.now()})
        GuardianLink.objects.get_or_create(guardian=users['outra.familia@example.invalid'],student=b,defaults={'verified_at':timezone.now()})
        pub={'author':users['direction'],'published_at':timezone.now(),'published':True}
        Notice.objects.get_or_create(title='Bem-vindos ao ambiente de demonstração',defaults={**pub,'content':'Este comunicado e todos os registros desta base são fictícios. Aqui a escola compartilha informações e pode solicitar confirmação de leitura.','require_read':True})
        Event.objects.get_or_create(title='Encontro de famílias · exemplo',defaults={**pub,'content':'Evento fictício para conhecer o calendário do portal.','date':today+timedelta(days=3),'category':'meeting'})
        Menu.objects.get_or_create(title='Cardápio de demonstração',defaults={**pub,'content':'Segunda: arroz, feijão, legumes e frango.\nTerça: arroz, feijão, abóbora e carne.\nExemplo de publicação; não corresponde ao cardápio real da escola.','week':today-timedelta(days=today.weekday()),'reviewed_by':'Equipe fictícia para demonstração'})
        Agenda.objects.get_or_create(student=a,date=today,defaults={'author':users['teacher'],'food':'Boa aceitação · registro fictício.','rest':'Descanso tranquilo · exemplo.','activities':'Exploração de cores e texturas.','school_note':'Este registro é apenas demonstrativo.'})
        Invoice.objects.get_or_create(external_id='DEMO-MENSALIDADE-A',defaults={'student':a,'competence':today.replace(day=1),'due_date':today.replace(day=10),'amount':'100.00'})
        self.stdout.write('Demonstração local preparada. Nenhum registro real foi importado.')
