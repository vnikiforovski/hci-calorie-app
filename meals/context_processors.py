from django.conf import settings


def static_version(request):
    """Adds STATIC_VERSION to every template, for ?v= on our own CSS and JS links,
    so the browser loads a changed file instead of an old cached copy."""
    return {'STATIC_VERSION': settings.STATIC_VERSION}
