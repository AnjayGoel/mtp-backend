from django.urls import path
from . import views

urlpatterns = [
    path('check/', views.get_user),
    path('', views.signup_or_update),
    path('eligible/', views.is_eligible)
]
