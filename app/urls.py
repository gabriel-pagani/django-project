from django.urls import path
from app.views import home_view, login_view, login_token_view, logout_view, otp_setup_view

app_name = 'app'

urlpatterns = [
    path('', home_view, name='home'),
    path('login/', login_view, name='login'),
    path('login/token/', login_token_view, name='login-token'),
    path('logout/', logout_view, name='logout'),
    path('two-factor/', otp_setup_view, name='otp-setup'),
]
