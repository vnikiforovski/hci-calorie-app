"""
URL configuration for zalak project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from meals import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('diary/', views.diary, name='diary'),
    path('statistics/', views.statistics, name='statistics'),
    path('profile/', views.profile, name='profile'),
    path('add/', views.add_meal, name='add_meal'),
    path('add/text/', views.text_input, name='text_input'),
    path('add/photo/', views.photo_input, name='photo_input'),
    path('photo/tips-seen/', views.photo_tips_seen, name='photo_tips_seen'),
    path('meal/<int:meal_id>/', views.result, name='result'),
    path('meal/<int:meal_id>/text/', views.text_input, name='edit_text'),
    path('meal/<int:meal_id>/photo/', views.photo_input, name='edit_photo'),
    path('meal/<int:meal_id>/retry/', views.retry, name='retry'),
    path('meal/<int:meal_id>/error/', views.analysis_error, name='analysis_error'),
    path('meal/<int:meal_id>/no-food/', views.no_food, name='no_food'),
    path('meal/<int:meal_id>/item/<int:item_id>/', views.edit_item, name='edit_item'),
    path('meal/<int:meal_id>/item/<int:item_id>/delete/', views.delete_item, name='delete_item'),
    path('meal/<int:meal_id>/undo-remove/', views.undo_remove_item, name='undo_remove_item'),
    path('meal/<int:meal_id>/log/', views.log_meal, name='log_meal'),
    path('meal/<int:meal_id>/undo-log/', views.undo_log, name='undo_log'),
    path('meal/<int:meal_id>/discard/', views.just_checking, name='just_checking'),
    path('style/', views.style, name='style'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
