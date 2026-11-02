from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from .models import Meal, Profile, slot_for_time


@receiver(pre_save, sender=Meal)
def fill_slot_from_time(sender, instance, **kwargs):
    # A meal without a slot gets one from the time it was eaten (FR8)
    if not instance.slot:
        instance.slot = slot_for_time(instance.eaten_at)


@receiver(pre_save, sender=Meal)
def count_logged_meals(sender, instance, raw=False, **kwargs):
    # The only place that changes Profile.meals_logged: the views, the admin
    # and the guest sign-up all go through save(), so they all pass here.
    if raw or instance.user_id is None:
        return   # loaddata brings its own counter; a guest has no Profile

    old_status = 'draft'   # a new meal counts as coming from draft
    if instance.pk:
        saved = Meal.objects.filter(pk=instance.pk).values_list('status', flat=True).first()
        if saved:
            old_status = saved

    if old_status == instance.status:
        return

    # get_or_create, not get: accounts made before chunk 12 (e.g. the first superuser)
    # never went through create_profile below
    profile, created = Profile.objects.get_or_create(user_id=instance.user_id)
    if old_status == 'draft' and instance.status == 'logged':
        profile.meals_logged += 1
    elif old_status == 'logged' and instance.status == 'draft':
        # Undo after Log: it never counted, so log - undo - log still counts once
        profile.meals_logged = max(profile.meals_logged - 1, 0)
    profile.save()


@receiver(post_delete, sender=Meal)
def remove_photo_file(sender, instance, **kwargs):
    # post_delete: the row is really gone (also after a bulk delete in the admin),
    # so the photo file in media/ can go too. Just checking leaves nothing behind.
    if instance.photo:
        instance.photo.delete(save=False)


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, raw=False, **kwargs):
    # Every new account gets its Profile, however it was made: sign-up, the admin
    # or createsuperuser. Only on create, so a later save (e.g. last_login) does nothing.
    if created and not raw:
        Profile.objects.create(user=instance)


@receiver(user_logged_in)
def keep_guest_meal(sender, request, user, **kwargs):
    # T7: a guest tapped Log, then made an account or signed in. One receiver catches every
    # way in: sign-up's login(), the LoginView and "Sign in instead". login() gave the session
    # a new key but kept its data, so the draft is found by what log_meal saved before.
    waiting = request.session.pop('guest_meal', None) if request is not None else None
    if not waiting:
        return
    meal = Meal.objects.filter(
        id=waiting['id'], user=None, session_key=waiting['session_key'],
        status='draft', deleted_at__isnull=True,
    ).first()
    if meal is None:
        return   # discarded or cleaned up in the meantime
    meal.user = user
    meal.session_key = ''
    meal.status = 'logged'
    meal.save()   # count_logged_meals above counts it, like any other Log
    request.session['kept_meal_id'] = meal.id   # Home shows "Logged to lunch · Undo"
