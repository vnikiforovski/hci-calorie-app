from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .units import UNIT_CHOICES, round_to


class Profile(models.Model):
    ACTIVITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    UNCERTAINTY_CHOICES = [
        ('ask', 'Ask me'),
        ('guess', 'Best guess'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    height_cm = models.PositiveIntegerField(null=True, blank=True)
    weight_kg = models.PositiveIntegerField(null=True, blank=True)
    activity_level = models.CharField(max_length=10, choices=ACTIVITY_CHOICES, blank=True)
    uncertainty = models.CharField(max_length=10, choices=UNCERTAINTY_CHOICES, default='ask')
    food_preferences = models.CharField(max_length=200, blank=True)  # sent to the AI (FR38)
    show_lighter_ideas = models.BooleanField(default=True)
    seen_photo_tips = models.BooleanField(default=False)
    meals_logged = models.PositiveIntegerField(default=0)  # set only by the signal

    def __str__(self):
        return self.user.username


class Meal(models.Model):
    SLOT_CHOICES = [
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('snack', 'Snack'),
        ('dinner', 'Dinner'),
    ]

    INPUT_CHOICES = [
        ('text', 'Text'),
        ('photo', 'Photo'),
        ('voice', 'Voice'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('logged', 'Logged'),
    ]

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='meals')
    session_key = models.CharField(max_length=40, blank=True)  # owner while a guest
    slot = models.CharField(max_length=10, choices=SLOT_CHOICES, blank=True)  # empty -> set from the time (signal)
    input_method = models.CharField(max_length=10, choices=INPUT_CHOICES)
    text = models.TextField(blank=True)  # typed/dictated text, or the photo note
    photo = models.ImageField(upload_to='meals/', null=True, blank=True)
    title = models.CharField(max_length=120, blank=True)
    description = models.CharField(max_length=200, blank=True)  # neutral line (FR15)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    eaten_at = models.DateTimeField(default=timezone.now)
    is_favorite = models.BooleanField(default=False)
    ai_response = models.JSONField(null=True, blank=True)  # validated AI output, for "Reset"
    deleted_at = models.DateTimeField(null=True, blank=True)  # soft delete for Undo
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-eaten_at']

    def __str__(self):
        return self.title or f"{self.get_slot_display() or 'Meal'} on {self.eaten_at.strftime('%Y-%m-%d %H:%M')}"

    def _total(self, name):
        return sum(getattr(item, name) for item in self.items.all())

    @property
    def kcal_min(self):
        return self._total('kcal_min')

    @property
    def kcal_max(self):
        return self._total('kcal_max')

    @property
    def protein_min(self):
        return self._total('protein_min')

    @property
    def protein_max(self):
        return self._total('protein_max')

    @property
    def carbs_min(self):
        return self._total('carbs_min')

    @property
    def carbs_max(self):
        return self._total('carbs_max')

    @property
    def fat_min(self):
        return self._total('fat_min')

    @property
    def fat_max(self):
        return self._total('fat_max')


class MealItem(models.Model):
    CONFIDENCE_CHOICES = [
        ('sure', 'Sure'),
        ('likely', 'Likely'),
        ('unsure', 'Unsure'),
    ]

    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES)
    grams = models.PositiveIntegerField()
    kcal_min_100g = models.PositiveIntegerField()
    kcal_max_100g = models.PositiveIntegerField()
    protein_min_100g = models.DecimalField(max_digits=5, decimal_places=1)
    protein_max_100g = models.DecimalField(max_digits=5, decimal_places=1)
    carbs_min_100g = models.DecimalField(max_digits=5, decimal_places=1)
    carbs_max_100g = models.DecimalField(max_digits=5, decimal_places=1)
    fat_min_100g = models.DecimalField(max_digits=5, decimal_places=1)
    fat_max_100g = models.DecimalField(max_digits=5, decimal_places=1)
    confidence = models.CharField(max_length=10, choices=CONFIDENCE_CHOICES)
    reason = models.CharField(max_length=150, blank=True)  # required when unsure
    question = models.CharField(max_length=150, blank=True)
    edited_by_user = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return f"{self.name} ({self.grams} g)"

    def _scale(self, per_100g, step):
        return round_to(per_100g * self.grams / 100, step)

    @property
    def kcal_min(self):
        return self._scale(self.kcal_min_100g, 10)

    @property
    def kcal_max(self):
        return self._scale(self.kcal_max_100g, 10)

    @property
    def protein_min(self):
        return self._scale(self.protein_min_100g, 1)

    @property
    def protein_max(self):
        return self._scale(self.protein_max_100g, 1)

    @property
    def carbs_min(self):
        return self._scale(self.carbs_min_100g, 1)

    @property
    def carbs_max(self):
        return self._scale(self.carbs_max_100g, 1)

    @property
    def fat_min(self):
        return self._scale(self.fat_min_100g, 1)

    @property
    def fat_max(self):
        return self._scale(self.fat_max_100g, 1)
