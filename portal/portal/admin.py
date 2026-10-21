import secrets
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm,UserChangeForm
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone
from .models import *
from .access import students_for,authorized_students,tickets_for,audit

admin.site.site_header='Flecha · Administração do portal'
admin.site.site_title='Flecha'
admin.site.index_title='Publicações, vínculos e atendimento'

class AddUser(forms.ModelForm):
    class Meta:model=User;fields=['email','first_name','last_name','role']
    def save(self,commit=True):
        user=super().save(commit=False)
        user.set_password(secrets.token_urlsafe(48))
        if commit:user.save()
        return user
class EditUser(UserChangeForm):
    class Meta:model=User;fields=['email','first_name','last_name','role','is_active']
@admin.register(User)
class Accounts(UserAdmin):
    add_form=AddUser;form=EditUser
    ordering=['email'];list_display=['email','first_name','role','is_active'];search_fields=['email','first_name']
    list_filter=['role','is_active']
    fieldsets=((None,{'fields':['email','password']}),('Identificação',{'fields':['first_name','last_name','role','is_active']}))
    add_fieldsets=((None,{'classes':['wide'],'fields':['email','first_name','last_name','role']}),)
    filter_horizontal=()
    def has_module_permission(self,request):return request.user.role in ('technical','direction')
    def has_view_permission(self,request,obj=None):return self.has_module_permission(request) and (obj is None or request.user.role=='technical' or obj.role=='guardian')
    has_change_permission=has_view_permission
    def has_add_permission(self,request):return self.has_module_permission(request)
    def has_delete_permission(self,request,obj=None):return False
    def get_queryset(self,request):
        qs=super().get_queryset(request)
        return qs if request.user.role=='technical' else qs.filter(role='guardian')
    def get_form(self,request,obj=None,**kwargs):
        form=super().get_form(request,obj,**kwargs)
        if request.user.role=='direction' and 'role' in form.base_fields:form.base_fields['role'].choices=[('guardian','Responsável')]
        return form
    def save_model(self,request,obj,form,change):
        if request.user.role=='direction' and obj.role!='guardian':raise PermissionDenied()
        super().save_model(request,obj,form,change);audit(request.user,'user.update',obj)

class ScopedAdmin(admin.ModelAdmin):
    roles=set()
    readonly_fields=()
    actions=None
    def has_module_permission(self,request):return request.user.role in self.roles
    def has_view_permission(self,request,obj=None):
        if not self.has_module_permission(request):return False
        return obj is None or self.get_queryset(request).filter(pk=obj.pk).exists()
    has_change_permission=has_view_permission
    def has_add_permission(self,request):return self.has_module_permission(request)
    def has_delete_permission(self,request,obj=None):return False
    def formfield_for_foreignkey(self,db_field,request,**kwargs):
        if db_field.related_model==Student:kwargs['queryset']=authorized_students(request.user)
        if db_field.related_model==Classroom and request.user.role=='teacher':kwargs['queryset']=Classroom.objects.filter(staff=request.user)
        if db_field.related_model==Invoice:kwargs['queryset']=Invoice.objects.filter(student__in=students_for(request.user,True))
        if db_field.name=='guardian':kwargs['queryset']=User.objects.filter(role='guardian')
        if db_field.name=='assigned_to':
            roles=['finance'] if request.user.role=='finance' else ['pedagogy','teacher','direction']
            kwargs['queryset']=User.objects.filter(role__in=roles,is_active=True)
        return super().formfield_for_foreignkey(db_field,request,**kwargs)
    def save_model(self,request,obj,form,change):
        if hasattr(obj,'author_id') and not change:obj.author=request.user
        if hasattr(obj,'uploaded_by_id') and not change:obj.uploaded_by=request.user
        if request.user.role=='teacher':
            classroom=getattr(obj,'classroom',None) or getattr(getattr(obj,'student',None),'classroom',None)
            if classroom is None or not classroom.staff.filter(pk=request.user.pk).exists():raise PermissionDenied()
        if change and 'file' in form.changed_data and isinstance(obj,Document):obj.approved=False;obj.published=False
        obj.full_clean();super().save_model(request,obj,form,change);audit(request.user,'admin.update' if change else 'admin.create',obj)
@admin.register(Classroom)
class Classrooms(ScopedAdmin):
    roles={'direction','pedagogy'};list_display=['name','stage','external_id'];filter_horizontal=['staff']
@admin.register(Student)
class Students(ScopedAdmin):
    roles={'direction','pedagogy','finance'};list_display=['name','classroom','period','active'];list_filter=['classroom','active'];search_fields=['name','external_id']
@admin.register(GuardianLink)
class Links(ScopedAdmin):
    roles={'direction'};list_display=['guardian','student','can_school','can_finance','active','verified_at']
@admin.register(Notice,Event,Menu)
class Publications(ScopedAdmin):
    roles={'direction','pedagogy','teacher'};list_display=['title','classroom','published','published_at','author'];readonly_fields=['author']
    def get_queryset(self,request):
        qs=super().get_queryset(request)
        return qs.filter(classroom__staff=request.user).distinct() if request.user.role=='teacher' else qs
    def get_form(self,request,obj=None,**kwargs):
        form=super().get_form(request,obj,**kwargs)
        if request.user.role=='teacher':form.base_fields['classroom'].required=True
        return form
@admin.register(Agenda)
class Agendas(ScopedAdmin):
    roles={'direction','pedagogy','teacher'};list_display=['student','date','author','updated_at'];readonly_fields=['author','updated_at'];list_filter=['date']
    def get_queryset(self,request):return super().get_queryset(request).filter(student__in=students_for(request.user))
    def get_form(self,request,obj=None,**kwargs):
        form=super().get_form(request,obj,**kwargs)
        if obj:
            for key in ('food','rest','activities','pedagogy','school_note'):
                if key not in obj.allowed_fields():form.base_fields.pop(key,None)
        return form
@admin.register(FamilyMessage)
class Messages(ScopedAdmin):
    roles={'direction','pedagogy','teacher'};list_display=['student','created_at'];readonly_fields=['student','author','text','created_at']
    def has_add_permission(self,request):return False
    def get_queryset(self,request):return super().get_queryset(request).filter(student__in=students_for(request.user))
@admin.register(Invoice)
class Invoices(ScopedAdmin):
    roles={'finance'};list_display=['student','competence','due_date','amount','status'];list_filter=['status','competence']
@admin.register(PaymentProof)
class Proofs(ScopedAdmin):
    roles={'finance'};list_display=['invoice','status','approved','uploaded_at'];readonly_fields=['invoice','file','uploaded_by','uploaded_at','review_file']
    def has_add_permission(self,request):return False
    @admin.display(description='Verificação do arquivo em quarentena')
    def review_file(self,obj):
        from django.utils.html import format_html
        from django.urls import reverse
        return format_html('<a href="{}">Baixar para conferência em ambiente protegido</a>',reverse('review_file',args=['proof',obj.pk]))
@admin.register(Document)
class Documents(ScopedAdmin):
    roles={'direction','pedagogy','finance'};list_display=['title','student','classroom','finance_only','approved','published'];readonly_fields=['uploaded_by','uploaded_at','review_file']
    def get_queryset(self,request):
        qs=super().get_queryset(request)
        return qs.filter(finance_only=request.user.role=='finance')
    def get_form(self,request,obj=None,**kwargs):
        form=super().get_form(request,obj,**kwargs)
        form.base_fields['finance_only'].disabled=True
        form.base_fields['finance_only'].initial=request.user.role=='finance'
        return form
    def save_model(self,request,obj,form,change):
        obj.finance_only=request.user.role=='finance';super().save_model(request,obj,form,change)
    @admin.display(description='Verificação do arquivo em quarentena')
    def review_file(self,obj):
        if not obj.pk:return 'Salve sem publicar antes de verificar o arquivo.'
        from django.utils.html import format_html
        from django.urls import reverse
        return format_html('<a href="{}">Baixar para conferência em ambiente protegido</a>',reverse('review_file',args=['document',obj.pk]))
@admin.register(Ticket)
class Tickets(ScopedAdmin):
    roles={'direction','pedagogy','teacher','finance'};list_display=['protocol','subject','category','status','assigned_to'];readonly_fields=['student','requester','category','subject','content','created_at','updated_at'];list_filter=['status','category']
    def get_queryset(self,request):return tickets_for(request.user)
    def has_add_permission(self,request):return False
@admin.register(ReadConfirmation)
class Reads(ScopedAdmin):
    roles={'direction','pedagogy'};list_display=['notice','user','read_at'];readonly_fields=['notice','user','read_at']
    def has_add_permission(self,request):return False
@admin.register(Audit)
class Audits(ScopedAdmin):
    roles={'technical','direction'};list_display=['created_at','actor','action','model','object_id'];readonly_fields=['created_at','actor','action','model','object_id']
    def has_add_permission(self,request):return False
