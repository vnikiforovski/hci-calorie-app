from django.shortcuts import render


def home(request):
    return render(request, 'base.html')


# Placeholders until their chunk is built, so the navigation never breaks.

def diary(request):
    return render(request, 'coming_soon.html', {'title': 'Diary'})


def statistics(request):
    return render(request, 'coming_soon.html', {'title': 'Statistics'})


def profile(request):
    return render(request, 'coming_soon.html', {'title': 'Profile'})


def add_meal(request):
    return render(request, 'coming_soon.html', {'title': 'Add meal'})


# Temporary style page (remove in chunk 19).

def style(request):
    swatches = ['bg', 'card', 'tint', 'line', 'accent', 'ink', 'muted',
                'water', 'protein', 'carbs', 'fat',
                'peach', 'butter', 'lilac', 'sky', 'danger', 'danger-bg']
    return render(request, 'style.html', {'swatches': swatches})
