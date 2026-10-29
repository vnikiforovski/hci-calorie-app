from django.contrib import admin

from .models import Profile, Meal, MealItem


class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "activity_level", "uncertainty", "meals_logged")
    readonly_fields = ("meals_logged",)  # only the signal changes it

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)


class MealItemInline(admin.TabularInline):
    model = MealItem
    extra = 1


class MealAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "slot", "status", "eaten_at", "kcal_range")
    list_filter = ("status", "slot")
    inlines = [MealItemInline]

    @admin.display(description="Calories")
    def kcal_range(self, obj):
        return f"{obj.kcal_min}–{obj.kcal_max} kcal"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    def has_change_permission(self, request, obj=None):
        if obj and not request.user.is_superuser and obj.user != request.user:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status == 'logged':
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if not change and (not request.user.is_superuser or not obj.user_id):
            obj.user = request.user
        super().save_model(request, obj, form, change)


admin.site.register(Profile, ProfileAdmin)
admin.site.register(Meal, MealAdmin)
