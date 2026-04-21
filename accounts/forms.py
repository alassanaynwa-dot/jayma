"""Formulaires d'authentification dashboard."""
from django import forms
from django.contrib.auth import authenticate


class LoginForm(forms.Form):
    """Login par username ou email + mot de passe."""

    identifier = forms.CharField(
        label="Nom d'utilisateur ou email",
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "ton-identifiant",
            "autofocus": "autofocus",
            "autocomplete": "username",
        }),
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            "class": "input",
            "placeholder": "••••••••",
            "autocomplete": "current-password",
        }),
    )

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        identifier = data.get("identifier")
        password = data.get("password")
        if not identifier or not password:
            return data

        # Autoriser identifier = email ou username
        from django.contrib.auth import get_user_model
        User = get_user_model()
        username = identifier
        if "@" in identifier:
            found = User.objects.filter(email__iexact=identifier).first()
            if found:
                username = found.username

        user = authenticate(self.request, username=username, password=password)
        if user is None:
            raise forms.ValidationError("Identifiants incorrects.")
        if not user.is_active:
            raise forms.ValidationError("Ce compte est désactivé.")

        self.user = user
        return data
