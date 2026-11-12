from django.conf import settings
from django.utils import timezone

from .models import slot_for_time


def static_version(request):
    """Adds STATIC_VERSION to every template, for ?v= on our own CSS and JS links,
    so the browser loads a changed file instead of an old cached copy."""
    return {'STATIC_VERSION': settings.STATIC_VERSION}


def toast(request):
    """The toast a view left in the session (e.g. "Logged to lunch · Undo"), shown once:
    popping it means a reload doesn't show it again. Used by templates/meals/_toast.html."""
    return {'toast': request.session.pop('toast', None)}


def add_meal(request):
    """The Add meal sheet is on every page of a signed-in user: the corner "+" and the
    sidebar's "Add a meal" open it. Its slot comes from the time; Home adds add_day on a past day.
    Recent is the last 5 different logged meals, each with one-tap Log again."""
    if not request.user.is_authenticated:
        return {}
    from .views import SLOT_OPTIONS, recent_meals   # here, not at the top: views.py is big and imports a lot
    return {'add_slot': slot_for_time(timezone.now()), 'slot_options': SLOT_OPTIONS,
            'recent_meals': recent_meals(request.user)}
