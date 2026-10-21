from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import FamilyMessage,PaymentProof,Ticket
class EmailLoginForm(AuthenticationForm):
    username=forms.EmailField(label='E-mail',widget=forms.EmailInput(attrs={'autocomplete':'username'}))
    password=forms.CharField(label='Senha',strip=False,widget=forms.PasswordInput(attrs={'autocomplete':'current-password'}))
    error_messages={'invalid_login':'E-mail ou senha inválidos. Confira os dados e tente novamente.','inactive':'Não foi possível acessar esta conta. Procure a secretaria.'}
    def clean_username(self):return self.cleaned_data['username'].strip().lower()
class MessageForm(forms.ModelForm):
    class Meta:model=FamilyMessage;fields=['text'];widgets={'text':forms.Textarea(attrs={'rows':3})}
class ProofForm(forms.ModelForm):
    class Meta:model=PaymentProof;fields=['file']
class TicketForm(forms.ModelForm):
    class Meta:model=Ticket;fields=['category','subject','content'];widgets={'content':forms.Textarea(attrs={'rows':5})}
class TicketReplyForm(forms.Form):
    content=forms.CharField(label='Informações complementares',max_length=2000,widget=forms.Textarea(attrs={'rows':4}))
