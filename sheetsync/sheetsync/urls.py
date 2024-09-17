# """
# URL configuration for sheetsync project.

# The urlpatterns list routes URLs to views. For more information please see:
#     https://docs.djangoproject.com/en/5.1/topics/http/urls/
# Examples:
# Function views
#     1. Add an import:  from my_app import views
#     2. Add a URL to urlpatterns:  path('', views.home, name='home')
# Class-based views
#     1. Add an import:  from other_app.views import Home
#     2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
# Including another URLconf
#     1. Import the include() function: from django.urls import include, path
#     2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
# """
# from django.contrib import admin
# from django.urls import path
# from . import views

# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('sync-google-sheet/', views.sync_google_sheet, name='sync_google_sheet'),
#     path('update-google-sheet/', views.update_google_sheet, name='update_google_sheet'),
#     path('webhook/notify/', views.webhook_notify_update, name='webhook_notify')
# ]

from django.urls import path
from . import views

urlpatterns = [
    path('sync-google-sheet/', views.sync_google_sheet, name='sync_google_sheet'),
    path('update-google-sheet/', views.update_google_sheet, name='update_google_sheet'),
    path('webhook/notify/', views.webhook_notify_update, name='webhook_notify'),
    path('process-webhook-queue/', views.process_webhook_queue, name='process_webhook_queue'),  # Add this line
]
