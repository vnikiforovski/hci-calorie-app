from django.db.models.signals import pre_save, post_delete
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

    # get_or_create: the Profile signal for new users only arrives in chunk 12
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
