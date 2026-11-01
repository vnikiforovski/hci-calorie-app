import uuid
from io import BytesIO

from django import forms
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Meal

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
        photo = self.cleaned_data['photo']
        if not isinstance(photo, UploadedFile):
            return photo                       # no new file: the draft keeps its photo
        if photo.size > PHOTO_MAX_BYTES:
            raise forms.ValidationError('That photo is too large. Try another one.')
        try:
            return shrink_photo(photo)
        except (UnidentifiedImageError, OSError):
            raise forms.ValidationError("Zalak can't read that file. Try another photo.")

    def clean_text(self):
        return self.cleaned_data['text'].strip()   # the note is optional
