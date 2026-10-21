from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractUser,BaseUserManager
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from .validators import validate_file,private_path

STAFF_ROLES=frozenset({'general_admin','technical','direction','finance','pedagogy','teacher'})

class UserManager(BaseUserManager):
    use_in_migrations=True
    def create_user(self,email,password=None,**extra):
        user=self.model(email=self.normalize_email(email).lower(),**extra)
        user.set_password(password);user.save(using=self._db);return user
    def create_superuser(self,email,password=None,**extra):
        extra.update(is_staff=True,is_superuser=True,role='technical')
        return self.create_user(email,password,**extra)
class User(AbstractUser):
    ROLES=[('guardian','Responsável'),('general_admin','Administrador geral'),('technical','Administração técnica'),('direction','Direção Geral'),('finance','Gestão Administrativa e Financeira'),('pedagogy','Coordenação Pedagógica'),('teacher','Professor ou auxiliar autorizado')]
    username=None
    email=models.EmailField('E-mail',unique=True)
    role=models.CharField('Perfil',max_length=20,choices=ROLES,default='guardian')
    USERNAME_FIELD='email'
    REQUIRED_FIELDS=[]
    objects=UserManager()
    def save(self,*args,**kwargs):
        self.email=self.email.strip().lower()
        self.is_staff=self.role in STAFF_ROLES
        super().save(*args,**kwargs)
    def __str__(self): return self.get_full_name() or self.email
    class Meta:
        constraints=[models.UniqueConstraint(models.functions.Lower('email'),name='email_case_insensitive')]

class Classroom(models.Model):
    name=models.CharField('Turma',max_length=100)
    stage=models.CharField('Etapa',max_length=20,choices=[('nursery','Berçário'),('early','Educação Infantil'),('year1','1º Ano')])
    staff=models.ManyToManyField(User,blank=True,related_name='classrooms',verbose_name='Equipe autorizada',limit_choices_to=Q(role__in=['general_admin','teacher','pedagogy','direction']))
    agenda_fields=models.JSONField('Campos da agenda',default=list,blank=True,help_text='Lista de chaves: food, rest, activities, pedagogy, school_note. Vazio usa padrão por etapa.')
    external_id=models.CharField('ID no sistema de gestão',max_length=100,unique=True,null=True,blank=True)
    def clean(self):
        allowed={'food','rest','activities','pedagogy','school_note'}
        if not isinstance(self.agenda_fields,list) or any(x not in allowed for x in self.agenda_fields): raise ValidationError({'agenda_fields':'Informe uma lista válida de campos da agenda.'})
        if len(self.agenda_fields)!=len(set(self.agenda_fields)): raise ValidationError({'agenda_fields':'Não repita campos.'})
    def __str__(self):return self.name

class Student(models.Model):
    name=models.CharField('Aluno',max_length=160)
    classroom=models.ForeignKey(Classroom,on_delete=models.PROTECT,verbose_name='Turma')
    period=models.CharField('Período contratado',max_length=100)
    active=models.BooleanField('Matrícula ativa',default=True)
    external_id=models.CharField('ID no sistema de gestão',max_length=100,unique=True,null=True,blank=True)
    def __str__(self):return self.name

class GuardianLink(models.Model):
    guardian=models.ForeignKey(User,on_delete=models.PROTECT,limit_choices_to={'role':'guardian'},verbose_name='Responsável')
    student=models.ForeignKey(Student,on_delete=models.PROTECT,verbose_name='Aluno')
    can_school=models.BooleanField('Pode consultar informações escolares',default=True)
    can_finance=models.BooleanField('Responsável financeiro autorizado',default=False)
    active=models.BooleanField('Vínculo autorizado',default=True)
    verified_at=models.DateTimeField('Vínculo conferido em',null=True,blank=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['guardian','student'],name='guardian_student_unique')]
    def clean(self):
        if self.guardian_id and self.guardian.role!='guardian':raise ValidationError('Vincule uma conta de responsável.')
        if self.active and not self.verified_at:raise ValidationError('Confira a autorização legal/cadastral e informe a data antes de liberar o vínculo.')
    def __str__(self):return f'{self.guardian} — {self.student}'

class Publication(models.Model):
    title=models.CharField('Título',max_length=180)
    content=models.TextField('Conteúdo')
    classroom=models.ForeignKey(Classroom,on_delete=models.PROTECT,null=True,blank=True,verbose_name='Turma destinatária (vazio = escola inteira)')
    author=models.ForeignKey(User,on_delete=models.PROTECT,editable=False,verbose_name='Publicado por')
    published_at=models.DateTimeField('Data de publicação')
    published=models.BooleanField('Publicado',default=False)
    class Meta:abstract=True;ordering=['-published_at','-pk']
class Notice(Publication):
    require_read=models.BooleanField('Solicitar confirmação de leitura',default=False)
    def __str__(self):return self.title
class ReadConfirmation(models.Model):
    notice=models.ForeignKey(Notice,on_delete=models.CASCADE)
    user=models.ForeignKey(User,on_delete=models.PROTECT)
    read_at=models.DateTimeField(auto_now_add=True)
    class Meta:constraints=[models.UniqueConstraint(fields=['notice','user'],name='unique_notice_read')]
class Event(Publication):
    date=models.DateField('Data do evento')
    category=models.CharField('Categoria',max_length=20,choices=[('holiday','Feriado'),('break','Recesso'),('meeting','Reunião'),('event','Evento'),('activity','Atividade')])
    def __str__(self):return f'{self.date} — {self.title}'
class Menu(Publication):
    week=models.DateField('Semana iniciada em')
    reviewed_by=models.CharField('Revisão nutricional',max_length=160)
    change_note=models.CharField('Alterações do cardápio',max_length=250,blank=True)
    def __str__(self):return f'{self.week} — {self.title}'
class Agenda(models.Model):
    student=models.ForeignKey(Student,on_delete=models.PROTECT,verbose_name='Aluno')
    date=models.DateField('Data')
    food=models.TextField('Alimentação',blank=True)
    rest=models.TextField('Sono e descanso',blank=True)
    activities=models.TextField('Atividades',blank=True)
    pedagogy=models.TextField('Observações pedagógicas',blank=True)
    school_note=models.TextField('Recados da escola',blank=True)
    author=models.ForeignKey(User,on_delete=models.PROTECT,editable=False)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:ordering=['-date'];constraints=[models.UniqueConstraint(fields=['student','date'],name='unique_student_daily_agenda')]
    def __str__(self):return f'{self.student} — {self.date}'
    def allowed_fields(self):
        c=self.student.classroom
        return c.agenda_fields or (['food','rest','activities','pedagogy','school_note'] if c.stage=='nursery' else ['activities','pedagogy','school_note'])
    def clean(self):
        if self.student_id:
            for key in ('food','rest','activities','pedagogy','school_note'):
                if key not in self.allowed_fields() and getattr(self,key):raise ValidationError({key:'Campo não habilitado para esta turma.'})
    def display_fields(self):return [(str(self._meta.get_field(k).verbose_name),getattr(self,k)) for k in self.allowed_fields() if getattr(self,k)]
class FamilyMessage(models.Model):
    student=models.ForeignKey(Student,on_delete=models.PROTECT)
    author=models.ForeignKey(User,on_delete=models.PROTECT,editable=False)
    text=models.TextField('Recado',max_length=3000)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:ordering=['-created_at']
class Invoice(models.Model):
    student=models.ForeignKey(Student,on_delete=models.PROTECT,verbose_name='Aluno')
    competence=models.DateField('Competência (primeiro dia do mês)')
    due_date=models.DateField('Vencimento')
    amount=models.DecimalField('Valor (R$)',max_digits=10,decimal_places=2,validators=[MinValueValidator(0)])
    status=models.CharField('Situação',max_length=15,choices=[('open','Em aberto'),('paid','Pago'),('cancelled','Cancelado')],default='open')
    reconciled_at=models.DateTimeField('Conciliação conferida em',null=True,blank=True)
    external_id=models.CharField('ID no sistema de gestão',max_length=100,unique=True,null=True,blank=True)
    class Meta:ordering=['-competence']
    def clean(self):
        if self.status=='paid' and not self.reconciled_at:raise ValidationError('Informe a conferência da conciliação antes de marcar como pago.')
        if self.competence and self.competence.day!=1:raise ValidationError('Use o primeiro dia do mês na competência.')
    def __str__(self):return f'{self.student} — {self.competence:%m/%Y}'
class PrivateFile(models.Model):
    file=models.FileField('Arquivo',upload_to=private_path,validators=[validate_file])
    approved=models.BooleanField('Arquivo verificado e liberado',default=False,help_text='Liberar somente após verificação de conteúdo, destinatários e segurança em ambiente protegido.')
    uploaded_by=models.ForeignKey(User,on_delete=models.PROTECT,editable=False)
    uploaded_at=models.DateTimeField(auto_now_add=True)
    class Meta:abstract=True
class Document(PrivateFile):
    title=models.CharField('Documento',max_length=180)
    student=models.ForeignKey(Student,on_delete=models.PROTECT,null=True,blank=True,verbose_name='Aluno (individual)')
    classroom=models.ForeignKey(Classroom,on_delete=models.PROTECT,null=True,blank=True,verbose_name='Turma (sem aluno = coletivo)')
    finance_only=models.BooleanField('Somente responsável financeiro',default=False)
    published=models.BooleanField('Publicado',default=False)
    def clean(self):
        if self.student_id and self.classroom_id:raise ValidationError('Escolha aluno ou turma, nunca ambos.')
    def __str__(self):return self.title
class PaymentProof(PrivateFile):
    invoice=models.ForeignKey(Invoice,on_delete=models.PROTECT,verbose_name='Mensalidade')
    status=models.CharField('Análise',max_length=15,choices=[('pending','Pendente de conciliação'),('reviewed','Analisado'),('rejected','Recusado')],default='pending')
    def __str__(self):return f'Comprovante #{self.pk} — {self.get_status_display()}'
class Ticket(models.Model):
    CATEGORIES=[('pedagogy','Atendimento pedagógico'),('administrative','Atendimento administrativo'),('finance','Atendimento financeiro'),('documents','Documentos e declarações'),('other','Outras solicitações')]
    student=models.ForeignKey(Student,on_delete=models.PROTECT,verbose_name='Aluno')
    requester=models.ForeignKey(User,on_delete=models.PROTECT,related_name='tickets',editable=False)
    category=models.CharField('Categoria',max_length=20,choices=CATEGORIES)
    subject=models.CharField('Assunto',max_length=180)
    content=models.TextField('Solicitação',max_length=5000)
    assigned_to=models.ForeignKey(User,on_delete=models.PROTECT,null=True,blank=True,related_name='assigned_tickets',verbose_name='Responsável pelo atendimento')
    status=models.CharField('Situação',max_length=15,choices=[('open','Aberta'),('progress','Em atendimento'),('waiting','Aguardando informações'),('done','Concluída')],default='open')
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    response=models.TextField('Resposta da escola',blank=True,max_length=5000)
    @property
    def protocol(self):return f'FLE-{self.created_at:%Y}-{self.pk:06d}'
    def __str__(self):return f'{self.protocol} — {self.subject}'
class Audit(models.Model):
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True)
    action=models.CharField(max_length=60)
    model=models.CharField(max_length=80,blank=True)
    object_id=models.CharField(max_length=40,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:ordering=['-created_at']
class AccessAttempt(models.Model):
    key=models.CharField(max_length=64,db_index=True)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
