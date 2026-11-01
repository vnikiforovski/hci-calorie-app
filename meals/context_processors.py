from django.conf import settings


def static_version(request):
    """Adds STATIC_VERSION to every template, for ?v= on our own CSS and JS links,
    so the browser loads a changed file instead of an old cached copy."""
    return {'STATIC_VERSION': settings.STATIC_VERSION}


def toast(request):
    """The toast a view left in the session (e.g. "Logged to lunch · Undo"), shown once:
    popping it means a reload doesn't show it again. Used by templates/meals/_toast.html."""
    return {'toast': request.session.pop('toast', None)}
