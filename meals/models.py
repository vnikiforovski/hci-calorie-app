from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .units import NO_PLURAL, UNIT_CHOICES, format_amount, round_to


def slot_for_time(dt):
    """Suggest a meal slot from the local time (FR8), with the hours from the Figma slot sheet.
    Also used by the signal in chunk 9."""
    local = timezone.localtime(dt)
    minutes = local.hour * 60 + local.minute
    if minutes < 10 * 60 + 30:
        return 'breakfast'
    if minutes < 15 * 60:
        return 'lunch'
    if minutes < 17 * 60 + 30:
        return 'snack'
    return 'dinner'


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
    weight_kg = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)  # 78.4 (chunk 18)
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True)  # Personal details (chunk 18)
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
        ('mine', 'My meal'),   # a template under Your meals (chunk 22): never counted anywhere
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
    def macro_rows(self):
        """One row per macro for the Result bars: solid up to min_pct, faded up to max_pct."""
        rows = [
            {'key': 'protein', 'name': 'Protein', 'min': self.protein_min, 'max': self.protein_max},
            {'key': 'carbs', 'name': 'Carbs', 'min': self.carbs_min, 'max': self.carbs_max},
            {'key': 'fat', 'name': 'Fat', 'min': self.fat_min, 'max': self.fat_max},
        ]
        # Scale against the largest max, so that macro's bar fills the whole width
        largest = max(row['max'] for row in rows)
        for row in rows:
            row['min_pct'] = round(row['min'] / largest * 100) if largest else 0
            row['max_pct'] = round(row['max'] / largest * 100) if largest else 0
        return rows

    @property
    def items_with_bars(self):
        """The items, each with the widths of its kcal bar, sized against the biggest item."""
        items = list(self.items.all())
        largest = max((item.kcal_max for item in items), default=0)
        for item in items:
            item.kcal_min_pct = round(item.kcal_min / largest * 100) if largest else 0
            item.kcal_max_pct = round(item.kcal_max / largest * 100) if largest else 0
        return items

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

    @property
    def portion(self):
        """'1 bowl · 300 g', '2 slices · 60 g', 'about 1 tbsp · 10 g' or just '300 g'."""
        if self.unit == 'g':
            return f"{self.grams} g"
        amount = format_amount(self.amount)  # 1.50 -> 1½, 2.00 -> 2
        label = self.get_unit_display()
        if self.amount > 1 and self.unit not in NO_PLURAL:
            label += 'es' if label.endswith('ch') else 's'
        about = 'about ' if self.confidence == 'unsure' else ''
        return f"{about}{amount} {label} · {self.grams} g"

    @property
    def ai_estimate(self):
        """What the AI said about this item (for Reset on Edit item), or None for an item
        the AI didn't give. Items keep the position they had in the AI answer."""
        items = (self.meal.ai_response or {}).get('items') or []
        if self.position < len(items):
            return items[self.position]
        return None

    # The chips under an unsure item's question: value, label, how much of Zalak's portion
    ANSWERS = [
        ('little', 'A little', Decimal('0.5')),
        ('about', 'About that', Decimal('1')),
        ('lot', 'A lot', Decimal('1.5')),
    ]

    @property
    def can_ask(self):
        """Show the question chips: Zalak is unsure, asked something, and its portion is known."""
        return self.confidence == 'unsure' and bool(self.question) and self.ai_estimate is not None

    def answer_portion(self, factor):
        """(amount, unit, grams) for a chip: always from Zalak's own portion, so taps don't add up."""
        ai = self.ai_estimate
        amount = (Decimal(str(ai['amount'])) * factor).quantize(Decimal('0.01'))
        grams = max(round_to(Decimal(str(ai['grams'])) * factor, 5), 5)
        return amount, ai['unit'], grams

    @property
    def known_portions(self):
        """Portions we know the grams of, as (amount, unit, grams): the AI's first, then the
        saved one. units.grams_for scales from the first in the same unit."""
        known = []
        ai = self.ai_estimate
        if ai:
            known.append((ai['amount'], ai['unit'], ai['grams']))
        known.append((self.amount, self.unit, self.grams))
        return known

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
