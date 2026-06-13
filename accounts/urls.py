from django.urls import path

from .views import register_page,login_page

from .api_views import (
    RegisterAPIView,
    LoginAPIView,
    LogoutAPIView
)

urlpatterns = [

    # HTML pages
    path(
        "register/",
        register_page,
        name="register-page"
    ),

    path(
        "login/",
        login_page,
        name="login-page"
    ),

    # APIs
    path(
        "api/register/",
        RegisterAPIView.as_view(),
        name="register-api"
    ),

    path(
        "api/login/",
        LoginAPIView.as_view(),
        name="login-api"
    ),

    path(
        "api/logout/",
        LogoutAPIView.as_view(),
        name="logout-api"
    ),
]