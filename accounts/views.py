from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django import forms
from .models import User

class RegisterForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Email address'}))
    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'placeholder': 'First name'}))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'placeholder': 'Last name'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm password'}))

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match!")
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email address already registered.")
        return email


class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Email address'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    error_message = None
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            password = form.cleaned_data['password']
            
            user = User.objects.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password
            )
            login(request, user)
            return redirect('dashboard')
        else:
            error_message = "Please correct the errors below."
    else:
        form = RegisterForm()
        
    return render(request, 'accounts/register.html', {'form': form, 'error_message': error_message})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    error_message = None
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
            else:
                error_message = "Invalid email or password."
        else:
            error_message = "Please enter valid credentials."
    else:
        form = LoginForm()
        
    return render(request, 'accounts/login.html', {'form': form, 'error_message': error_message})


def logout_view(request):
    logout(request)
    return redirect('login')
