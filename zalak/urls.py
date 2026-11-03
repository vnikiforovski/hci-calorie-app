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
from django.contrib.auth import views as auth_views
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from meals import views
from meals.forms import EmailAuthenticationForm

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    # Accounts (chunk 12). Sign in / Sign out are Django's built-in views, given our template and form.
    path('sign-in/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        authentication_form=EmailAuthenticationForm,
        redirect_authenticated_user=True,      # a signed-in user goes straight to Home
    ), name='sign_in'),
    path('sign-out/', auth_views.LogoutView.as_view(), name='sign_out'),   # POST only
    path('sign-up/', views.signup, name='signup'),
    path('sign-up/details/', views.signup_details, name='signup_details'),
    path('diary/', views.diary, name='diary'),
    # Your meals (chunk 22): the back of the Diary book, and one saved meal
    path('diary/your-meals/', views.your_meals, name='your_meals'),
    path('diary/your-meals/<int:meal_id>/', views.saved_meal, name='saved_meal'),
    path('diary/your-meals/<int:meal_id>/rename/', views.rename_saved, name='rename_saved'),
    path('diary/your-meals/<int:meal_id>/remove/', views.remove_saved, name='remove_saved'),
    path('diary/your-meals/<int:meal_id>/undo-remove/', views.undo_remove_saved, name='undo_remove_saved'),
    path('statistics/', views.statistics, name='statistics'),
    path('profile/', views.profile, name='profile'),
    # Profile (chunk 18): every name starts with "profile", so base.html marks the sidebar row on all of them
    path('profile/details/', views.profile_details, name='profile_details'),
    path('profile/preferences/', views.profile_preferences, name='profile_preferences'),
    path('profile/account/', views.account_privacy, name='profile_account'),
    path('profile/password/', views.change_password, name='profile_password'),
    path('profile/delete/', views.delete_account, name='profile_delete'),
    path('profile/help/', views.help_about, name='profile_help'),
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
    path('meal/<int:meal_id>/item/<int:item_id>/re-estimate/', views.re_estimate_item, name='re_estimate_item'),
    path('meal/<int:meal_id>/item/<int:item_id>/answer/', views.answer_question, name='answer_question'),
    path('meal/<int:meal_id>/add-item/', views.add_item, name='add_item'),
    path('meal/<int:meal_id>/undo-remove/', views.undo_remove_item, name='undo_remove_item'),
    # Tell Zalak (chunk 24): the whole meal corrected in the user's own words, with Undo
    path('meal/<int:meal_id>/tell/', views.tell_zalak, name='tell_zalak'),
    path('meal/<int:meal_id>/undo-tell/', views.undo_tell_zalak, name='undo_tell_zalak'),
    path('meal/<int:meal_id>/log/', views.log_meal, name='log_meal'),
    path('meal/<int:meal_id>/undo-log/', views.undo_log, name='undo_log'),
    path('meal/<int:meal_id>/discard/', views.just_checking, name='just_checking'),
    path('meal/<int:meal_id>/lighter-idea/hide/', views.hide_lighter_idea, name='hide_lighter_idea'),
    path('meal/<int:meal_id>/save/', views.save_meal, name='save_meal'),
    path('meal/<int:meal_id>/delete/', views.delete_meal, name='delete_meal'),
    path('meal/<int:meal_id>/undo-delete/', views.undo_delete_meal, name='undo_delete_meal'),
    path('meal/<int:meal_id>/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('meal/<int:meal_id>/log-again/', views.log_again, name='log_again'),
    path('meal/<int:meal_id>/undo-log-again/', views.undo_log_again, name='undo_log_again'),
    path('meal/<int:meal_id>/save-as-mine/', views.save_as_my_meal, name='save_as_my_meal'),
    path('meal/<int:meal_id>/save-mine/', views.save_my_meal, name='save_my_meal'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
