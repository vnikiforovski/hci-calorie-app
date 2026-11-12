# Django exam pattern + Zalak mapping

Oct 25, 2026 · @Viktor

## 1. How the exam is graded and the order to work in

The Django part is graded by `python manage.py check_solution` (64 tests in the Hospital exam), and the Bootstrap part is checked by hand. If the server does not start, nothing is graded. So keep the project compiling at every step and run the checker after each file.

The tests are the real spec. The task text never says `full_name` or `past_appointments`, but the tests check those exact names. Read the test names before writing a single model.

### Work order

1. **Read** the task and skim `hospital_app/tests/` for field, context and URL names. Run `check_solution` once to see the empty baseline.
2. **Settings** are usually done in the starter: `INSTALLED_APPS`, `TEMPLATES["DIRS"]`, `STATICFILES_DIRS`, `MEDIA_URL` / `MEDIA_ROOT`. Check them, don't rewrite them.
3. **models.py**, then `makemigrations` and `migrate`. Everything else imports the models, so they come first.
4. **admin.py**: register every model, then add the permission rules.
5. **signals.py**: the automatic rules. The starter's `apps.py` already imports signals in `ready()`. If it doesn't, the signals never fire.
6. **forms.py**: one `ModelForm` per form on the pages.
7. **views.py**: one function per page.
8. **urls.py**: one `path()` per view, with the exact `name=` the tests expect.
9. **Templates + Bootstrap**: `base.html`, then the list page, then the detail page.

Then run `createsuperuser`, `populate_db` (if provided), `runserver`, and `check_solution` again.

### Translating task sentences into Django

The main decision: if a rule says "without regard to whether it's from the admin panel or a form", it goes in a **signal**. If it is about the admin only, it goes in a **ModelAdmin method**.

| Phrase in the task | Django tool | File |
| --- | --- | --- |
| "one of: cardiologist, dermatologist, neurologist" | `CharField(choices=[...])` | models |
| "photo" | `ImageField(upload_to=...)` + Pillow + MEDIA settings | models, settings |
| "number of completed ..." | `PositiveIntegerField(default=0)` | models |
| "e-mail" | `EmailField` | models |
| "users are doctors" | `OneToOneField(User)` on the domain model | models |
| "has one responsible X" | `ForeignKey` | models |
| "can also have additional X (many)" | through table with two FKs + `unique_together` | models |
| "can be added only by ..." | `has_add_permission` | admin |
| "can be changed only by ..." | `has_change_permission(obj)` | admin |
| "can be deleted only if ..." | `has_delete_permission(obj)` | admin |
| "automatically becomes ..." (on admin save) | `save_model` | admin |
| "can see only their own ..." | `get_queryset` + `Q` + `distinct()` | admin |
| "automatically, whether from admin or form" | `pre_save` / `pre_delete` receiver | signals |
| "when X changes from A to B" | compare the old DB row with the new object | admin or signals |
| "form for adding; type is always ..." | `ModelForm` with `exclude`, set the field in the view | forms, views |
| "grouped by specialty" | one filtered queryset per group, one loop per group | views, templates |
| "past / today / future" | `datetime__lt`, `datetime__date`, `datetime__gt` with `timezone.now()` | views |

## 2. The Hospital solution, file by file

The official solution is about 250 lines of Python plus 3 templates. Each part below says what goes there and why. Code is slightly shortened from the official files.

### Step 3: models.py

Four models: `Doctor`, `Patient`, `Appointment`, and `AppointmentAssignment` (the assistants table).

```python
class Doctor(models.Model):
    SPECIALTY_CHOICES = [
        ('cardiologist', 'Cardiologist'),
        ('dermatologist', 'Dermatologist'),
        ('neurologist', 'Neurologist'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    specialty = models.CharField(max_length=20, choices=SPECIALTY_CHOICES)
    image = models.ImageField(upload_to="doctors/", null=True, blank=True)
    completed_appointments = models.PositiveIntegerField(default=0)
    email = models.EmailField()
    ...
    def __str__(self):
        return self.full_name
```

- **`choices`**: the first value is stored in the DB, the second is shown. Templates show the label with `get_specialty_display`.
- **`OneToOneField(User)`** links a logged-in account to a doctor. The admin rules use this link ("the user who adds it becomes the responsible doctor").
- **`__str__`** controls how the object appears in admin dropdowns and lists.

```python
class Appointment(models.Model):
    TYPE_CHOICES = [('cardiologist', 'Cardiology'), ...]   # same keys as SPECIALTY_CHOICES
    STATUS_CHOICES = [('scheduled', 'Scheduled'), ('in_progress', 'In Progress'), ('completed', 'Completed')]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    datetime = models.DateTimeField()
    note = models.TextField(blank=True, null=True)
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True)
    responsible_doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE,
                                           related_name='responsible_appointments')

class AppointmentAssignment(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    class Meta:
        unique_together = ('appointment', 'doctor')
```

- **Same keys in `TYPE_CHOICES` and `SPECIALTY_CHOICES`.** This is a deliberate trick: the view can write `appointment.appointment_type = doctor.specialty`.
- **`SET_NULL`** on patient means an appointment survives when its patient is deleted. The task needs this: in-progress appointments must stay for audit.
- **`related_name`**: Doctor already has two links to Appointment (responsible + assistant), so the reverse name must be explicit.
- **The through table** is many-to-many done by hand. `unique_together` stops the same doctor being added twice. The analogy: a sign-up sheet where each name can appear once per event.
- **`blank=True`** is about forms (the field may be empty). **`null=True`** is about the DB (the column may be NULL). Optional fields usually need both, except text fields.

### Step 4: admin.py

```python
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("appointment_type", "status", "datetime", "patient", "responsible_doctor")

    def has_add_permission(self, request):
        return Doctor.objects.filter(user=request.user).exists() or request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj:
            doctor = Doctor.objects.filter(user=request.user).first()
            return doctor is not None and obj.responsible_doctor == doctor
        return False

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status != 'scheduled':
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if not change:                      # creating
            obj.responsible_doctor = Doctor.objects.filter(user=request.user).first()
        else:                               # editing: compare with the DB version
            old = Appointment.objects.get(pk=obj.pk)
            if old.status == 'in_progress' and obj.status == 'completed':
                obj.responsible_doctor.completed_appointments += 1
                obj.responsible_doctor.save()
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        doctor = Doctor.objects.filter(user=request.user).first()
        if doctor is None:
            return qs.none()
        return qs.filter(Q(responsible_doctor=doctor) |
                         Q(appointmentassignment__doctor=doctor)).distinct()
```

- **`obj=None`**: Django calls permission methods once for the list page (no object) and once per object. Always handle both.
- **`change`** in `save_model` is `False` on create and `True` on edit. That one flag splits "set the owner" from "detect a status transition".
- **Detecting "A → B"**: `obj` already holds the new values, so you load the old row from the DB to compare.
- **`Q(...) | Q(...)`** is SQL `OR`. **`.distinct()`** removes duplicates when the join matches twice.
- **`appointmentassignment__doctor`**: the double underscore follows a relation backwards, using the lowercase model name.
- Call `super().save_model(...)` last, or nothing is saved.

### Step 5: signals.py

```python
@receiver(pre_save, sender=Appointment)
def appointment_status_adjustment(sender, instance, **kwargs):
    if instance.status == 'completed' and instance.datetime > now():
        instance.status = 'scheduled'
    if instance.status == 'scheduled' and instance.datetime < now():
        instance.status = 'completed'
    if instance.pk is None and instance.patient_id is not None:   # bonus, only on create
        patient_ids = (Appointment.objects
            .filter(responsible_doctor=instance.responsible_doctor,
                    patient__institution=instance.patient.institution)
            .values_list('patient_id', flat=True).distinct())
        if len(patient_ids) >= 3:
            instance.note = f"High workload with patients from institution {instance.patient.institution}."

@receiver(pre_delete, sender=Patient)
def cleanup_appointments(sender, instance, **kwargs):
    for appt in Appointment.objects.filter(patient=instance):
        if appt.status == 'scheduled':
            appt.delete()
        elif appt.status == 'in_progress':
            appt.note = "Patient record missing - appointment preserved for audit purposes."
            appt.save()
```

- **`pre_save`** fires right before every `.save()`, from the admin, a form or the shell. You edit `instance` and Django saves your edits. You don't call `save()` here, or it loops forever.
- **`instance.pk is None`** means "this is a new object". It is the signal's version of `change=False`.
- **`pre_delete` vs `post_delete`**: after deletion, `SET_NULL` has already cut the link, so the patient's appointments can't be found any more. Use `pre_` when you need the relations.
- **`.values_list('patient_id', flat=True).distinct()`** gives a plain list of unique IDs, the cheapest way to count distinct things.
- Signals only work because `apps.py` has `def ready(self): from . import signals`.

### Step 6: forms.py

```python
class AppointmentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
    class Meta:
        model = Appointment
        exclude = ['responsible_doctor', 'appointment_type']
```

- **`exclude`** hides fields the user must not choose, because the view sets them. That is how "the type is always the doctor's specialty" is enforced.
- **The `__init__` loop** puts Bootstrap's `form-control` on every input. The tests check for it, and it is a pattern you reuse on every form.

### Step 7: views.py

```python
def index(request):
    context = {
        'cardiologists': Doctor.objects.filter(specialty='cardiologist'),
        'dermatologists': Doctor.objects.filter(specialty='dermatologist'),
        'neurologists': Doctor.objects.filter(specialty='neurologist'),
    }
    return render(request, 'index.html', context)

def doctor_detail(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)      # object in memory, not in DB yet
            appointment.responsible_doctor = doctor
            appointment.appointment_type = doctor.specialty
            appointment.save()
            AppointmentAssignment.objects.create(appointment=appointment, doctor=doctor)
            return redirect('doctor_detail', doctor_id=doctor.id)
    form = AppointmentForm()

    now = timezone.now()
    qs = Appointment.objects.filter(responsible_doctor=doctor)
    context = {
        'doctor': doctor, 'form': form,
        'past_appointments': qs.filter(datetime__lt=now, status='completed'),
        'today_appointments': qs.filter(datetime__date=now.date()),
        'future_appointments': qs.filter(datetime__gt=now, status='scheduled'),
    }
    return render(request, 'doctor_detail.html', context)
```

- **`get_object_or_404`** returns a 404 page for an unknown ID instead of a crash. A test checks this.
- **`commit=False`** is the standard way to fill excluded fields before saving. The analogy: you fill in the form, the clerk adds the stamp, then files it.
- **`redirect` after a POST** (Post/Redirect/Get) stops a browser refresh from submitting the form twice.
- **Field lookups**: `__lt`, `__gt`, `__date`. Same syntax as `__institution` in signals, just comparing instead of following a relation.

### Step 8: urls.py

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path('', views.index, name='index'),
    path('doctors/<int:doctor_id>/', views.doctor_detail, name='doctor_detail'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

- **`<int:doctor_id>`** must match the view's parameter name exactly.
- **`name=`** is what `{% url 'doctor_detail' doctor.id %}` and `redirect()` use.
- **`+ static(...)`** serves uploaded images in development. Without it, `doctor.image.url` gives a broken image.

### Step 9: templates + Bootstrap

- **`base.html`** loads Bootstrap with `{% load static %}` and `{% static 'bootstrap/css/bootstrap.css' %}`. It holds the navbar, the footer and `{% block content %}{% endblock %}`.
- **Child pages** start with `{% extends 'base.html' %}` and fill the `content` block.
- **List page**: one `<h2>` + `<div class="row">` per specialty. Inside it, `{% for doctor in cardiologists %}` renders a `col-md-4` card with `rounded-circle` image, a `badge`, and an `btn-outline-success` link to `{% url 'doctor_detail' doctor.id %}`.
- **Detail page**: a `bg-success text-white` header section, then a `row` with three `col-md-4` columns (past / today / future). Each column loops with `{% for %}...{% empty %}No appointments.{% endfor %}`.
- **The form**: `<form method="post">`, `{% csrf_token %}` (Django refuses the POST without it), `{{ form.as_p }}`, and a submit button.
- **Filters used**: `{{ appt.datetime|time }}`, `{{ doctor.get_specialty_display }}`.
- **Bootstrap classes worth memorizing** from this page: `container`, `row`, `col-md-4`, `card`, `card-body`, `card-title`, `badge`, `btn btn-success`, `navbar`, `py-5`, `mb-4`, `text-center`, `bg-light`, `shadow`, `rounded`.

## 3. Weak spots in the official solution

The solution passes all 64 tests (I ran it), but it has six flaws. Keep the exam version for the exam, and fix these in Zalak.

| Problem | What happens | Fix |
| --- | --- | --- |
| Invalid POST is replaced by a blank form | `form = AppointmentForm()` runs after a failed `is_valid()`, so validation errors never show | Create the blank form only in an `else:` branch for GET |
| `{{ doctor.image.url }}` with no image | `image` is `null=True`, so a doctor without a photo crashes the page | Wrap it in `{% if doctor.image %}` with a placeholder |
| Footer year is empty | `{{ now\|date:"Y" }}` reads a `now` variable that no view sends | Use the tag `{% now "Y" %}` |
| Status flip runs on every save | The task says "when adding", but `pre_save` also fires on edits. A counter can be incremented in `save_model` and the status then flipped back | Guard with `if instance.pk is None` if the rule is create-only |
| Date-time typed as plain text | `DateTimeField` renders as a text box, so users must type `2025-05-28 12:31` | `widgets = {'datetime': forms.DateTimeInput(attrs={'type': 'datetime-local'})}` |
| Card markup pasted 3 times | Any change to the card must be made in three places | One `{% include 'doctor_card.html' %}` inside each loop |

One more quirk the tests require: the view adds the responsible doctor as their own assistant (`AppointmentAssignment.objects.create(...)`). Do it in the exam because a test checks it, but it is not a pattern to copy.

## 4. Mapping each pattern to Zalak

Every pattern from the Hospital exam has a natural place in Zalak, so you will practice the full exam toolkit while building the app. This is a proposal to discuss, not a final design.

### Proposed models (sketch)

```python
class Profile(models.Model):                      # like Doctor.user
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    daily_calorie_goal = models.PositiveIntegerField(default=2000)
    meals_logged = models.PositiveIntegerField(default=0)   # like completed_appointments

class Meal(models.Model):                         # like Appointment
    MEAL_TYPE_CHOICES = [('breakfast', 'Breakfast'), ('lunch', 'Lunch'),
                         ('dinner', 'Dinner'), ('snack', 'Snack')]
    INPUT_CHOICES = [('photo', 'Photo'), ('text', 'Text'), ('voice', 'Voice')]
    STATUS_CHOICES = [('estimated', 'Estimated'), ('confirmed', 'Confirmed')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meals')
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPE_CHOICES, blank=True)
    input_method = models.CharField(max_length=10, choices=INPUT_CHOICES)
    image = models.ImageField(upload_to='meals/', null=True, blank=True)
    description = models.TextField(blank=True)
    eaten_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='estimated')
    note = models.TextField(blank=True, null=True)

class MealItem(models.Model):                     # one food in a meal
    CONFIDENCE_CHOICES = [('high', 'High'), ('medium', 'Medium'), ('low', 'Low')]
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=100)
    portion_grams = models.PositiveIntegerField()
    calories = models.PositiveIntegerField()
    protein_g = models.DecimalField(max_digits=6, decimal_places=1)
    carbs_g = models.DecimalField(max_digits=6, decimal_places=1)
    fat_g = models.DecimalField(max_digits=6, decimal_places=1)
    confidence = models.CharField(max_length=10, choices=CONFIDENCE_CHOICES)
    edited_by_user = models.BooleanField(default=False)
```

### Exam pattern → Zalak

| Exam pattern (Hospital) | Zalak equivalent | File |
| --- | --- | --- |
| `Doctor.user` OneToOne | `Profile.user`, holds the daily goal | models |
| `choices` (specialty, status) | `meal_type`, `input_method`, `status`, `confidence` | models |
| `ImageField` + MEDIA | `Meal.image` for photo input | models, settings |
| Counter with `default=0` | `Profile.meals_logged` | models |
| FK + `related_name` | `MealItem.meal` → `meal.items.all` in templates | models |
| `has_add_permission` superuser-only | Only superusers add or edit other users' profiles | admin |
| `has_change_permission(obj)` owner-only | Users change only their own meals | admin |
| `has_delete_permission` by status | Confirmed meals can't be deleted from admin (optional) | admin |
| `save_model` auto-owner | `obj.user = request.user` when a meal is created | admin |
| `save_model` detects A → B | `estimated` → `confirmed` increments `meals_logged` | admin + view |
| `get_queryset` filtered | Non-superusers see only their own meals | admin |
| `pre_save` adjusts by datetime | Empty `meal_type` is set from the hour of `eaten_at` (7–10 breakfast, 11–15 lunch, ...) | signals |
| Bonus auto-note | Any `low`-confidence item sets the note "Some items are uncertain, check the portions" | signals |
| `pre_delete` cleanup | Deleting a meal also deletes its photo file from disk | signals |
| `ModelForm` + `exclude` + form-control loop | `MealForm` (excludes `user`, `status`), `MealItemForm` for portion edits | forms |
| Index grouped by specialty | Today page grouped by meal type: breakfast / lunch / dinner / snacks | views, templates |
| `get_object_or_404` detail + POST form | Meal result page with the portion-adjust form. Use `get_object_or_404(Meal, id=meal_id, user=request.user)` | views |
| `commit=False` then set fields | `meal.user = request.user`, then call the AI and create the items | views |
| Past / today / future buckets | History: today / yesterday / earlier with `eaten_at__date` | views |
| Redirect after POST | After logging a meal, redirect to its result page | views |
| `base.html` + `extends` | Zalak base with the sage navbar and caramel accent | templates |
| Cards, badges, grid | Meal cards, confidence badges (green / amber / grey), macros in three `col` columns | templates |

### Open decisions for you

1. **Food catalog?** Adding a `Food` model (name, kcal per 100 g) would make `MealItem` a real through table: `meal` + `food` + `portion_grams`, with `unique_together`. That is the exact exam pattern and it helps with fixing misidentified foods (pick from a list). The cost is one more model and seeding data.
2. **Store totals or compute them?** Stored totals updated by a `post_save` signal on `MealItem` = more signal practice. A `@property` that sums the items = simpler.
3. **Counter meaning.** `meals_logged` is neutral. Avoid counters like "days over goal", which feed the guilt pattern your research flagged.

## 5. What Zalak needs beyond the exam minimum

Seven additions, each needed because Zalak has real users and an AI call, which the exam doesn't.

1. **Login and logout.** Django's built-in `LoginView` / `LogoutView`, `LOGIN_URL` in settings, and `@login_required` on every page. The exam pages are public; Zalak's meals are personal.
2. **Photo upload from a page.** `<form method="post" enctype="multipart/form-data">` and `MealForm(request.POST, request.FILES)`. The Flight repo shows this; the Hospital exam had no upload.
3. **The Claude API call.** One function in its own `services.py`, e.g. `estimate_meal(image=None, text=None)` returning a list of items. The view stays short, the API key lives in an environment variable, and an API error shows a friendly message instead of a crash.
4. **Editing several items at once.** `inlineformset_factory(Meal, MealItem, fields=[...])` renders one row per food, so the user can fix every portion on one screen.
5. **Daily totals.** `aggregate(Sum('items__calories'))` over today's meals, to compare against `Profile.daily_calorie_goal`.
6. **Voice input.** The browser's Web Speech API fills the description field in JavaScript. The server only ever sees text, so no extra Django work.
7. **The Sage & caramel theme.** One `static/css/zalak.css` that overrides Bootstrap's CSS variables (`--bs-primary`, `--bs-body-bg`), loaded after `bootstrap.css` in `base.html`.

Suggested build order: models → admin → login → log-a-meal page with the AI call → result page with portion editing → today page → history → signals → theme polish. The core calorie-checking flow then works early, and every later step adds one exam pattern.
