from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from .models import Student, GuardianLink, Ticket, STAFF_ROLES

SCHOOL_ROLES={'direction','pedagogy','teacher'}

def can_administer_portal(user):
    return bool(user.is_authenticated and user.is_active and user.is_staff and user.role in STAFF_ROLES)
def students_for(user,financial=False):
    qs=Student.objects.filter(active=True).select_related('classroom')
    if not user.is_authenticated or not user.is_active:return qs.none()
    if user.role=='general_admin':return qs
    if user.role=='guardian':
        links=GuardianLink.objects.filter(guardian=user,active=True,verified_at__isnull=False,**({'can_finance':True} if financial else {'can_school':True}))
        return qs.filter(pk__in=links.values('student_id'))
    if financial:return qs if user.role=='finance' else qs.none()
    if user.role in ('direction','pedagogy'):return qs
    if user.role=='teacher':return qs.filter(classroom__staff=user).distinct()
    return qs.none()

def authorized_students(user):
    return (students_for(user)|students_for(user,financial=True)).distinct()

def visible_publications(model,user):
    # Usuários sem vínculo não ganham acesso a comunicados gerais.
    students=students_for(user)
    if not students.exists():return model.objects.none()
    return model.objects.filter(published=True,published_at__lte=timezone.now()).filter(Q(classroom=None)|Q(classroom_id__in=students.values('classroom_id')))

def tickets_for(user):
    qs=Ticket.objects.select_related('student','assigned_to','requester')
    if not user.is_authenticated or not user.is_active:return qs.none()
    if user.role=='general_admin':return qs
    if user.role=='guardian':return qs.filter(requester=user,student__in=authorized_students(user))
    if user.role=='finance':return qs.filter(category__in=['finance','administrative','documents','other'])
    if user.role in SCHOOL_ROLES:return qs.filter(student__in=students_for(user)).exclude(category='finance')
    return qs.none()

def navigation(request):
    from django.conf import settings
    user=request.user
    return {'local_mode':settings.LOCAL,'can_school':user.is_authenticated and students_for(user).exists(),
            'can_finance':user.is_authenticated and students_for(user,True).exists(),
            'is_portal_staff':can_administer_portal(user)}

def audit(user,action,obj=None):
    from .models import Audit
    Audit.objects.create(actor=user if user.is_authenticated else None,action=action,model=obj._meta.label if obj else '',object_id=str(obj.pk) if obj else '')
