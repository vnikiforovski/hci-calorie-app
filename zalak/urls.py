"""The project's URLs: the admin, sign in and out (Django's own views), the uploaded photos, and
every page of the meals app (meals/urls.py)."""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.static import serve

from meals.forms import EmailAuthenticationForm


def media_file(request, path):
    """An uploaded photo from media/, with Django's own file view."""
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path('admin/', admin.site.urls),
    # Sign in / Sign out are Django's built-in views, given our template and form
    path('sign-in/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        authentication_form=EmailAuthenticationForm,
        redirect_authenticated_user=True,      # a signed-in user goes straight to Home
    ), name='sign_in'),
    path('sign-out/', auth_views.LogoutView.as_view(), name='sign_out'),   # POST only
    # Uploaded photos. Django's static() helper only works while DEBUG is on, so the same view is
    # wired here directly: the photos also show when Zalak runs with DEBUG off (see README.md).
    re_path(r'^media/(?P<path>.*)$', media_file),
    path('', include('meals.urls')),
]
