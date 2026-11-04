from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import UsernameField
from django.core.exceptions import ValidationError
from django.views.decorators.debug import sensitive_variables

from .models import Evaluador


class EditarUsuarioForm(forms.ModelForm):
    version = forms.CharField(widget=forms.HiddenInput, max_length=64)
    new_password1 = forms.CharField(
        label='Nueva contraseña', required=False, strip=False, min_length=8, max_length=128,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='Usa al menos 8 caracteres. Evita contraseñas comunes, solo números o datos del usuario.',
    )
    new_password2 = forms.CharField(
        label='Confirmar nueva contraseña', required=False, strip=False, max_length=128,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model = Evaluador
        fields = ('username', 'first_name', 'last_name', 'email', 'cargo')
        field_classes = {'username': UsernameField}
        labels = {
            'username': 'Nombre de usuario', 'first_name': 'Nombre(s)',
            'last_name': 'Apellidos', 'email': 'Correo electrónico', 'cargo': 'Cargo',
        }
        widgets = {
            'username': forms.TextInput(attrs={'autocomplete': 'off', 'autocapitalize': 'none', 'spellcheck': 'false'}),
            'first_name': forms.TextInput(attrs={'autocomplete': 'off'}),
            'last_name': forms.TextInput(attrs={'autocomplete': 'off'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'off'}),
        }

    def clean_username(self):
        username = self.cleaned_data['username']
        if Evaluador.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Ya existe un usuario con ese nombre, incluso con otras mayúsculas.')
        return username

    @sensitive_variables('password', 'confirmation')
    def clean(self):
        data = super().clean()
        password = data.get('new_password1')
        confirmation = data.get('new_password2')
        if password and not confirmation and 'new_password2' not in self.errors:
            self.add_error('new_password2', 'Confirma la nueva contraseña.')
        elif confirmation and not password and 'new_password1' not in self.errors:
            self.add_error('new_password1', 'Escribe la nueva contraseña.')
        elif password and confirmation and password != confirmation:
            self.add_error('new_password2', 'Las contraseñas no coinciden.')
        return data

    @sensitive_variables('password')
    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get('new_password1')
        if password and 'new_password2' not in self.errors:
            # Valida contra los datos editados, aun si la instalación no define validadores.
            validators = password_validation.get_default_password_validators() or [
                password_validation.MinimumLengthValidator(),
                password_validation.UserAttributeSimilarityValidator(),
                password_validation.CommonPasswordValidator(),
                password_validation.NumericPasswordValidator(),
            ]
            try:
                password_validation.validate_password(password, self.instance, validators)
            except ValidationError as error:
                self.add_error('new_password1', error)
