from django import forms
from .models import Ticket, Message
from django.contrib.auth.models import User
import re

class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['title', 'description']



class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(attrs={
                "class": "form-control chat-input",
                "placeholder": "Scrivi un messaggio...",
                "rows": 3,
            })
        }


class CustomRegisterForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput())
    password2 = forms.CharField(widget=forms.PasswordInput())

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username già in uso.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email già registrata.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")

        if p1 != p2:
            raise forms.ValidationError("Le password non coincidono.")

        # --- Password policy ---
        # Minimo 8 caratteri, una maiuscola, una minuscola, un numero
        password_regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$'
        if not re.match(password_regex, p1):
            raise forms.ValidationError(
                "La password deve contenere almeno 8 caratteri, "
                "una maiuscola, una minuscola e un numero."
            )

        return cleaned
