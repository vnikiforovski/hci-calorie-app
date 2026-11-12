from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.timezone import now

from .forms import AppointmentForm
from .models import Doctor, Appointment, AppointmentAssignment


def index(request):
    cardiologists = Doctor.objects.filter(specialty='cardiologist')
    dermatologists = Doctor.objects.filter(specialty='dermatologist')
    neurologists = Doctor.objects.filter(specialty='neurologist')

    context = {
        'cardiologists': cardiologists,
        'dermatologists': dermatologists,
        'neurologists': neurologists,
    }
    return render(request, 'index.html', context)

def doctor_detail(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.responsible_doctor = doctor
            appointment.appointment_type = doctor.specialty
            appointment.save()
            AppointmentAssignment.objects.create(appointment=appointment, doctor=doctor)
            return redirect('doctor_detail', doctor_id=doctor.id)

    form = AppointmentForm()

    now = timezone.now()
    all_appointments = Appointment.objects.filter(responsible_doctor=doctor)
    past_appointments = all_appointments.filter(datetime__lt=now, status='completed')
    today_appointments = all_appointments.filter(datetime__date=now.date())
    future_appointments = all_appointments.filter(datetime__gt=now, status='scheduled')

    context = {
        'doctor': doctor,
        'form': form,
        'past_appointments': past_appointments,
        'today_appointments': today_appointments,
        'future_appointments': future_appointments,
    }
    return render(request, 'doctor_detail.html', context)