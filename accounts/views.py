from django.shortcuts import render

def register_page(request):
    return render(request, "accounts/register.html")

def login_page(request):
    return render(request, "accounts/login.html")