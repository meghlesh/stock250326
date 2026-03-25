from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.urls import path, include

def root_redirect(request):
    return redirect("/company/login/")
     
urlpatterns = [
    path("", root_redirect),
    path('django-admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('company/', include('company.urls')),
    path("inventory/", include("inventory.urls")),
]