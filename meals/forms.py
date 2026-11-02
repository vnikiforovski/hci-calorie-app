import uuid
from datetime import datetime
from io import BytesIO

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Meal, MealItem, Profile
from .units import MAX_GRAMS, grams_for

PHOTO_MAX_SIDE = 1568            # px on the long side: what the AI looks at anyway
PHOTO_MAX_BYTES = 20 * 1024 * 1024


class TextMealForm(forms.ModelForm):
    # Set to "voice" by voice.js once words were dictated (chunk 7). A plain hidden field,
    # not the model's choice field, so an odd value can't block the form with an error nobody sees.
    input_method = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Meal
        fields = ['text', 'slot', 'input_method']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control z-meal-text',
                'rows': 5,
                'placeholder': 'e.g. two eggs, toast with butter, coffee with milk',
                'aria-label': 'Describe your meal',
            }),
            'slot': forms.HiddenInput(),
        }

    def clean_text(self):
        text = self.cleaned_data['text'].strip()
        if not text:
            raise forms.ValidationError('Write what you ate, e.g. "two eggs and toast".')
        return text

    def clean_input_method(self):
        # This page only makes text and voice meals; anything else counts as typed text
        if self.cleaned_data.get('input_method') == 'voice':
            return 'voice'
        return 'text'


def shrink_photo(upload):
    """Turn a phone photo upright, shrink it to PHOTO_MAX_SIDE and save it as JPEG.
    A random name keeps a guest's photo from being guessed by its URL."""
    with Image.open(upload) as image:
        image = ImageOps.exif_transpose(image)   # phones often store photos sideways
        image = image.convert('RGB')             # JPEG has no transparency
        image.thumbnail((PHOTO_MAX_SIDE, PHOTO_MAX_SIDE))
        buffer = BytesIO()
        image.save(buffer, 'JPEG', quality=85)
    return ContentFile(buffer.getvalue(), name=f'{uuid.uuid4().hex}.jpg')


def clean_uploaded_photo(photo):
    """A new upload is checked and shrunk; anything else (no new file) is returned as it is.
    Used by Photo + note and by Meal detail."""
    if not isinstance(photo, UploadedFile):
        return photo
    if photo.size > PHOTO_MAX_BYTES:
        raise forms.ValidationError('That photo is too large. Try another one.')
    try:
        return shrink_photo(photo)
    except (UnidentifiedImageError, OSError):
        raise forms.ValidationError("Zalak can't read that file. Try another photo.")


class PhotoMealForm(forms.ModelForm):
    class Meta:
        model = Meal
        fields = ['photo', 'text', 'slot']
        widgets = {
            # Visually hidden: the shutter, Upload and Retake buttons open it (photo_preview.js)
            'photo': forms.FileInput(attrs={
                'accept': 'image/*',
                'class': 'visually-hidden',
                'tabindex': '-1',
            }),
            'text': forms.Textarea(attrs={
                'class': 'form-control z-meal-text',
                'rows': 4,
                'placeholder': 'e.g. cooked in butter, I ate half',
                'aria-labelledby': 'noteTitle',
            }),
            'slot': forms.HiddenInput(),
        }
        error_messages = {
            'photo': {
                'required': 'Take or choose a photo first.',
                'invalid_image': "Zalak can't read that file. Try another photo.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['photo'].required = True   # the model allows none (text meals)

    def clean_photo(self):
        # No new file: the draft keeps its photo
        return clean_uploaded_photo(self.cleaned_data['photo'])

    def clean_text(self):
        return self.cleaned_data['text'].strip()   # the note is optional


class MealDetailForm(forms.ModelForm):
    """Meal detail (chunk 15): the slot, the title and the photo of a logged meal, plus when it
    was eaten. The day and the time come from the time sheet (meal_detail.js) as two hidden
    fields; the view puts cleaned_data['eaten_at'] on the meal. The items save on their own."""
    eaten_day = forms.DateField(widget=forms.HiddenInput)
    eaten_time = forms.TimeField(widget=forms.HiddenInput)
    remove_photo = forms.BooleanField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Meal
        fields = ['slot', 'title', 'photo']
        widgets = {
            'slot': forms.HiddenInput(),   # set by the slot dropdown (slot_select.js)
            # form="mealForm": the fields sit around the page, the form is the bottom bar's
            'title': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off',
                                            'placeholder': 'e.g. Sunday lunch', 'form': 'mealForm'}),
            # Visually hidden: the Add / Replace photo buttons open it (meal_detail.js)
            'photo': forms.FileInput(attrs={'accept': 'image/*', 'class': 'visually-hidden', 'tabindex': '-1',
                                            'form': 'mealForm'}),
        }
        labels = {'title': 'Meal name'}
        error_messages = {
            'photo': {'invalid_image': "Zalak can't read that file. Try another photo."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            eaten = timezone.localtime(self.instance.eaten_at)
            self.initial['eaten_day'] = eaten.date()
            self.initial['eaten_time'] = eaten.time().replace(second=0, microsecond=0)

    def clean_title(self):
        return self.cleaned_data['title'].strip()   # empty: the view gives back Zalak's title

    def clean_photo(self):
        return clean_uploaded_photo(self.cleaned_data['photo'])

    def clean(self):
        cleaned = super().clean()
        day, time = cleaned.get('eaten_day'), cleaned.get('eaten_time')
        if day and time:
            eaten_at = timezone.make_aware(datetime.combine(day, time))
            if eaten_at > timezone.now():
                raise forms.ValidationError("That time hasn't come yet. Pick an earlier one.")
            cleaned['eaten_at'] = eaten_at
        return cleaned


class MealItemForm(forms.ModelForm):
    """Edit item: the name, the amount and the unit. The grams follow from them
    (units.grams_for); the per-100 g values stay, so a rename keeps the numbers."""

    class Meta:
        model = MealItem
        fields = ['name', 'amount', 'unit']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control z-name-field', 'autocomplete': 'off'}),
            # Both are set by portion.js: the stepper and the Unit sheet
            'amount': forms.HiddenInput(),
            'unit': forms.HiddenInput(),
        }
        error_messages = {
            'name': {'required': 'Write what the food is, e.g. "white bread".'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Read before the form changes the instance: grams_for scales from these
        self.known = self.instance.known_portions

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if not name:
            raise forms.ValidationError('Write what the food is, e.g. "white bread".')
        return name

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount is None or amount <= 0:
            raise forms.ValidationError('The amount must be more than 0.')
        return amount

    def clean(self):
        cleaned = super().clean()
        amount, unit = cleaned.get('amount'), cleaned.get('unit')
        if amount and unit:
            grams = grams_for(amount, unit, self.known)
            if grams > MAX_GRAMS:
                self.add_error('amount', "That's more than 5 kg. Check the amount.")
            cleaned['grams'] = grams
        return cleaned


# ---------- Accounts (chunk 12) ----------

# Calmer words for Django's password validators (AUTH_PASSWORD_VALIDATORS in settings), by error code
PASSWORD_HINTS = {
    'password_too_short': 'Use at least 8 characters.',
    'password_too_common': 'Lots of people use this password. Try a few words only you would put together.',
    'password_entirely_numeric': 'Add some letters, not only numbers.',
    'password_too_similar': 'Make it less like your name or e-mail.',
}


class SignUpForm(forms.ModelForm):
    """Create account, step 1 (Figma "Create account · 1 of 2"): name, e-mail, password
    and the "estimates, not medical advice" checkbox (FR33). The e-mail is the username,
    so the view sets user.username and the hashed password after save(commit=False)."""

    password = forms.CharField(
        strip=False,
        # A hint under the field instead of Figma's placeholder: it stays while typing,
        # and auth.js ticks it once there are 8 characters
        help_text='At least 8 characters',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password',
        }),
        error_messages={'required': 'Choose a password, at least 8 characters.'},
    )
    agree = forms.BooleanField(
        label='I understand Zalak gives estimates, not medical advice.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={'required': 'Tick this box to continue.'},
    )

    class Meta:
        model = User
        fields = ['first_name', 'email']
        labels = {'first_name': 'Your name', 'email': 'E-mail'}
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'autocomplete': 'given-name',
                'autofocus': True,
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'autocomplete': 'email',
                'inputmode': 'email',
                'placeholder': 'you@example.com',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Both are optional on Django's User, but Zalak needs them
        self.fields['first_name'].required = True
        self.fields['email'].required = True
        self.fields['first_name'].error_messages['required'] = 'Write your name, so Zalak knows what to call you.'
        self.fields['email'].error_messages['required'] = 'Write your e-mail. You sign in with it.'
        self.fields['email'].error_messages['invalid'] = 'That doesn\'t look like an e-mail. Check it, e.g. ana@example.com.'

    def clean_first_name(self):
        return self.cleaned_data['first_name'].strip()

    def clean_email(self):
        # Lowercase, so Ana@Example.com and ana@example.com are one account
        email = self.cleaned_data['email'].strip().lower()
        if len(email) > 150:   # the username column is 150 long
            raise forms.ValidationError('That e-mail is too long. Use a shorter one.')
        if User.objects.filter(username__iexact=email).exists():
            # The code lets the template add a "Sign in instead" link under this message
            raise forms.ValidationError('There is already an account with this e-mail.', code='taken')
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        if password:
            # Django's validators from settings: length, too common, all numbers,
            # and too close to the name or e-mail (so they get an unsaved user to compare)
            user = User(username=cleaned.get('email', ''), email=cleaned.get('email', ''),
                        first_name=cleaned.get('first_name', ''))
            try:
                validate_password(password, user)
            except forms.ValidationError as error:
                # Django says what is wrong; Zalak also says what to do (docs/05). Unknown codes keep Django's text.
                for problem in error.error_list:
                    message = PASSWORD_HINTS.get(problem.code, ' '.join(problem.messages))
                    self.add_error('password', message)
        return cleaned


class ProfileDetailsForm(forms.ModelForm):
    """Create account, step 2 (Figma "A bit about you"): all optional, so an empty form is fine."""

    class Meta:
        model = Profile
        fields = ['height_cm', 'weight_kg', 'activity_level']
        labels = {'height_cm': 'Height', 'weight_kg': 'Weight', 'activity_level': 'How active are you?'}
        widgets = {
            'height_cm': forms.NumberInput(attrs={
                'class': 'form-control z-unit-field', 'inputmode': 'numeric', 'placeholder': '170',
            }),
            'weight_kg': forms.NumberInput(attrs={
                'class': 'form-control z-unit-field', 'inputmode': 'numeric', 'placeholder': '70',
            }),
            # Bootstrap's btn-check hides the radio; its label is the segment (signup_2.html)
            'activity_level': forms.RadioSelect(attrs={'class': 'btn-check'}),
        }
        error_messages = {
            'height_cm': {'invalid': 'Write the height as a whole number, e.g. 170.'},
            'weight_kg': {'invalid': 'Write the weight as a whole number, e.g. 70.'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Without the "---------" choice a ModelForm adds for blank=True: nothing ticked means "not said"
        self.fields['activity_level'].choices = Profile.ACTIVITY_CHOICES

    def clean_height_cm(self):
        height = self.cleaned_data['height_cm']
        if height is not None and not 100 <= height <= 250:
            raise forms.ValidationError('Check the height: Zalak expects 100 to 250 cm.')
        return height

    def clean_weight_kg(self):
        weight = self.cleaned_data['weight_kg']
        if weight is not None and not 30 <= weight <= 300:
            raise forms.ValidationError('Check the weight: Zalak expects 30 to 300 kg.')
        return weight


class EmailAuthenticationForm(AuthenticationForm):
    """Sign in with the e-mail (it is the username) and calm, action-based messages (docs/05)."""

    error_messages = {
        'invalid_login': 'That e-mail and password don\'t match. Check them and try again.',
        'inactive': 'This account is switched off. Ask the admin to turn it back on.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        username = self.fields['username']
        username.label = 'E-mail'
        username.widget = forms.EmailInput(attrs={
            'class': 'form-control',
            'autocomplete': 'email',
            'inputmode': 'email',
            'autofocus': True,
            'placeholder': 'you@example.com',
        })
        username.error_messages['required'] = 'Write the e-mail you signed up with.'
        password = self.fields['password']
        password.widget.attrs.update({'class': 'form-control'})
        password.error_messages['required'] = 'Write your password.'

    def get_invalid_login_error(self):
        # Wrong password: the e-mail stays filled in, so start again at the password
        self.fields['username'].widget.attrs.pop('autofocus', None)
        self.fields['password'].widget.attrs['autofocus'] = True
        return super().get_invalid_login_error()

    def clean_username(self):
        # Ana@Example.com finds ana@example.com. Sign-up saves e-mails in lowercase, but an
        # account made in the admin (e.g. the superuser "Viktor") may have capitals, so look it up.
        username = self.cleaned_data['username'].strip()
        saved = User.objects.filter(username__iexact=username).values_list('username', flat=True).first()
        return saved or username
