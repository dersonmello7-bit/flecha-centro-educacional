import calendar
from datetime import date,timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView,PasswordResetView
from django.db.models import Q
from django.http import FileResponse,Http404
from django.shortcuts import get_object_or_404,redirect,render
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.http import require_POST
from .models import *
from .forms import *
from .access import students_for,authorized_students,visible_publications,tickets_for,audit

def throttled(request,scope):
    email=request.POST.get('username',request.POST.get('email','')).strip().lower()[:254]
    # Não confia em X-Forwarded-For fornecido pelo visitante.
    keys=[salted_hmac('access',scope+email).hexdigest(),salted_hmac('access',scope+request.META.get('REMOTE_ADDR','')).hexdigest()]
    since=timezone.now()-timedelta(minutes=15)
    limit=5 if scope=='login' else 3
    if any(AccessAttempt.objects.filter(key=k,created_at__gte=since).count()>=limit for k in keys):return True
    AccessAttempt.objects.bulk_create([AccessAttempt(key=k) for k in keys])
    return False

class PortalLogin(LoginView):
    template_name='registration/login.html'
    authentication_form=EmailLoginForm
    redirect_authenticated_user=True
    def post(self,request,*args,**kwargs):
        if throttled(request,'login'):
            return render(request,'registration/limited.html',status=429)
        return super().post(request,*args,**kwargs)
    def form_valid(self,form):
        result=super().form_valid(form);audit(self.request.user,'login');return result

class PortalReset(PasswordResetView):
    template_name='registration/password_reset_form.html'
    email_template_name='registration/password_reset_email.txt'
    subject_template_name='registration/password_reset_subject.txt'
    def post(self,request,*args,**kwargs):
        if not (settings.EMAIL_READY or settings.TESTING):
            messages.info(request,'O envio de e-mails ainda não está configurado nesta instalação local. Procure a administração.');return redirect('password_reset')
        if throttled(request,'reset'):return render(request,'registration/limited.html',status=429)
        return super().post(request,*args,**kwargs)

@login_required
def dashboard(request):
    students=authorized_students(request.user)
    selected=students.first()
    if request.GET.get('aluno'):
        if not request.GET['aluno'].isascii() or not request.GET['aluno'].isdigit() or len(request.GET['aluno'])>12:raise Http404()
        selected=get_object_or_404(students,pk=request.GET['aluno'])
    if request.user.role!='guardian':
        return render(request,'portal/staff.html',{'count':students.count()})
    notices=visible_publications(Notice,request.user)
    events=visible_publications(Event,request.user).filter(date__gte=timezone.localdate()).order_by('date')
    invoice=None
    selected_school=False
    if selected:
        selected_school=students_for(request.user).filter(pk=selected.pk).exists()
        notices=notices.filter(Q(classroom=None)|Q(classroom=selected.classroom))
        events=events.filter(Q(classroom=None)|Q(classroom=selected.classroom))
        if not selected_school:notices=notices.none();events=events.none()
        if students_for(request.user,True).filter(pk=selected.pk).exists():invoice=Invoice.objects.filter(student=selected).first()
    audit(request.user,'dashboard')
    return render(request,'portal/dashboard.html',{'students':students,'selected':selected,'selected_school':selected_school,'notices':notices[:4],'events':events[:4],'invoice':invoice})

@login_required
def notices(request):
    return render(request,'portal/notices.html',{'items':visible_publications(Notice,request.user),'confirmed':list(ReadConfirmation.objects.filter(user=request.user).values_list('notice_id',flat=True))})
@login_required
@require_POST
def confirm_read(request,pk):
    notice=get_object_or_404(visible_publications(Notice,request.user),pk=pk,require_read=True)
    ReadConfirmation.objects.get_or_create(notice=notice,user=request.user)
    audit(request.user,'notice.read',notice);messages.success(request,'Leitura confirmada.');return redirect('notices')

@login_required
def events(request):
    try:year,month=map(int,request.GET.get('mes',timezone.localdate().strftime('%Y-%m')).split('-'));start=date(year,month,1)
    except (ValueError,TypeError):raise Http404()
    if year<2000 or year>2100:raise Http404()
    items=visible_publications(Event,request.user).filter(date__year=year,date__month=month).order_by('date')
    mapping={}
    for event in items:mapping.setdefault(event.date.day,[]).append(event)
    weeks=[[(day,mapping.get(day,[])) for day in week] for week in calendar.Calendar().monthdayscalendar(year,month)]
    return render(request,'portal/events.html',{'items':items,'weeks':weeks,'month':start,'mode':request.GET.get('modo','lista')})
@login_required
def menus(request):return render(request,'portal/menus.html',{'items':visible_publications(Menu,request.user).order_by('-week')})

@login_required
def agenda(request,pk):
    student=get_object_or_404(students_for(request.user),pk=pk)
    form=MessageForm(request.POST or None)
    if request.method=='POST':
        if request.user.role!='guardian':raise Http404()
        if form.is_valid():
            obj=form.save(commit=False);obj.student=student;obj.author=request.user;obj.save();audit(request.user,'message.create',obj);messages.success(request,'Recado enviado à equipe.');return redirect('agenda',pk=pk)
    qs=Agenda.objects.filter(student=student).select_related('author','student__classroom')
    date_filter=request.GET.get('data','')
    if date_filter:
        try:qs=qs.filter(date=date.fromisoformat(date_filter))
        except ValueError:raise Http404()
    # Recados enviados por outra conta responsável não são expostos.
    family_messages=FamilyMessage.objects.filter(student=student)
    if request.user.role=='guardian':family_messages=family_messages.filter(author=request.user)
    return render(request,'portal/agenda.html',{'student':student,'items':qs[:90],'recados':family_messages[:20],'form':form})

@login_required
def finance(request):
    qs=Invoice.objects.filter(student__in=students_for(request.user,True)).select_related('student')
    return render(request,'portal/finance.html',{'items':qs,'authorized':students_for(request.user,True).exists()})
@login_required
def proof(request,pk):
    invoice=get_object_or_404(Invoice.objects.filter(student__in=students_for(request.user,True)),pk=pk)
    form=ProofForm(request.POST or None,request.FILES or None)
    if request.method=='POST' and form.is_valid():
        obj=form.save(commit=False);obj.invoice=invoice;obj.uploaded_by=request.user;obj.save();audit(request.user,'proof.upload',obj)
        messages.success(request,'Comprovante recebido, pendente de conciliação. O envio não confirma quitação.');return redirect('finance')
    return render(request,'portal/form.html',{'title':'Enviar comprovante','intro':'PDF, JPG ou PNG, até 10 MB. O pagamento só será confirmado após conciliação financeira.','form':form})

def documents_for(user):
    school=students_for(user);financial=students_for(user,True)
    qs=Document.objects.filter(published=True,approved=True)
    scope=Q(student__in=school)|Q(student=None,classroom_id__in=school.values('classroom_id'))
    if school.exists():scope|=Q(student=None,classroom=None)
    scope=(scope & Q(finance_only=False)) | (Q(student__in=financial)&Q(finance_only=True))
    if financial.exists():scope|=Q(finance_only=True,student=None,classroom=None)|Q(finance_only=True,student=None,classroom_id__in=financial.values('classroom_id'))
    return qs.filter(scope).distinct()
@login_required
def documents(request):return render(request,'portal/documents.html',{'items':documents_for(request.user)})
@login_required
def download(request,kind,pk):
    if kind=='document':obj=get_object_or_404(documents_for(request.user),pk=pk)
    elif kind=='proof':obj=get_object_or_404(PaymentProof.objects.filter(approved=True,invoice__student__in=students_for(request.user,True)),pk=pk)
    else:raise Http404()
    try:response=FileResponse(obj.file.open('rb'),as_attachment=True,filename=f'flecha-{kind}-{obj.pk}'+__import__('pathlib').Path(obj.file.name).suffix)
    except FileNotFoundError:raise Http404()
    audit(request.user,'file.download',obj);return response

@login_required
def review_file(request,kind,pk):
    if kind=='proof' and request.user.role=='finance':obj=get_object_or_404(PaymentProof,pk=pk)
    elif kind=='document' and request.user.role in ('direction','pedagogy','finance'):
        obj=get_object_or_404(Document,pk=pk,finance_only=request.user.role=='finance')
    else:raise Http404()
    try:response=FileResponse(obj.file.open('rb'),as_attachment=True,filename=f'quarentena-{obj.pk}'+__import__('pathlib').Path(obj.file.name).suffix)
    except FileNotFoundError:raise Http404()
    audit(request.user,'file.review_download',obj);return response

@login_required
def stored_file(request,key):
    document=Document.objects.filter(file=key).first()
    if document:
        if request.user.role in ('direction','pedagogy','finance') and document.finance_only==(request.user.role=='finance'):
            return review_file(request,'document',document.pk)
        return download(request,'document',document.pk)
    proof=PaymentProof.objects.filter(file=key).first()
    if proof:
        if request.user.role=='finance':return review_file(request,'proof',proof.pk)
        return download(request,'proof',proof.pk)
    raise Http404()

def health(request):
    from django.db import connection
    from django.http import JsonResponse
    try:
        with connection.cursor() as cursor:cursor.execute('SELECT 1');cursor.fetchone()
    except Exception:return JsonResponse({'status':'unavailable'},status=503)
    return JsonResponse({'status':'ok'})

@login_required
def tickets(request):return render(request,'portal/tickets.html',{'items':tickets_for(request.user)})
@login_required
def new_ticket(request,pk):
    student=get_object_or_404(authorized_students(request.user),pk=pk)
    form=TicketForm(request.POST or None)
    if not students_for(request.user,True).filter(pk=pk).exists():form.fields['category'].choices=[c for c in Ticket.CATEGORIES if c[0]!='finance']
    if request.method=='POST' and form.is_valid():
        if form.cleaned_data['category']=='finance' and not students_for(request.user,True).filter(pk=pk).exists():raise Http404()
        obj=form.save(commit=False);obj.student=student;obj.requester=request.user;obj.save();audit(request.user,'ticket.create',obj);messages.success(request,f'Solicitação registrada: {obj.protocol}.');return redirect('tickets')
    return render(request,'portal/form.html',{'title':'Nova solicitação','intro':str(student),'form':form})
@login_required
def ticket(request,pk):
    obj=get_object_or_404(tickets_for(request.user),pk=pk)
    form=TicketReplyForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        extra='\n\nComplemento '+timezone.localtime().strftime('%d/%m/%Y %H:%M')+':\n'+form.cleaned_data['content']
        if len(obj.content)+len(extra)>20000:form.add_error('content','Limite de complementos atingido. Abra uma nova solicitação citando este protocolo.')
        else:
            obj.content+=extra;obj.status='open';obj.save();audit(request.user,'ticket.reply',obj);return redirect('ticket',pk=pk)
    return render(request,'portal/ticket.html',{'item':obj,'form':form})
