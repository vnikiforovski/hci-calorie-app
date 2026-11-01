from django import forms

from .models import Meal


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
