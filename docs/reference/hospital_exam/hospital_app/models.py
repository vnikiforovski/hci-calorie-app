from django.db import models
from django.contrib.auth.models import User

class Doctor(models.Model):
    SPECIALTY_CHOICES = [
        ('cardiologist', 'Cardiologist'),
        ('dermatologist', 'Dermatologist'),
        ('neurologist', 'Neurologist'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    specialty = models.CharField(max_length=20, choices=SPECIALTY_CHOICES)
    institution = models.CharField(max_length=100)
    image = models.ImageField(upload_to="doctors/", null=True, blank=True)
    completed_appointments = models.PositiveIntegerField(default=0)
    email = models.EmailField()
    phone = models.CharField(max_length=20)

    def __str__(self):
        return self.full_name


class Patient(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]

    full_name = models.CharField(max_length=100)
    birth_date = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    email = models.EmailField()
    institution = models.CharField(max_length=100)

    def __str__(self):
        return self.full_name


class Appointment(models.Model):
    TYPE_CHOICES = [
        ('cardiologist', 'Cardiology'),
        ('dermatologist', 'Dermatology'),
        ('neurologist', 'Neurology'),
    ]

    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    appointment_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    datetime = models.DateTimeField()
    note = models.TextField(blank=True, null=True)
    patient = models.ForeignKey(
        Patient, on_delete=models.SET_NULL, null=True, blank=True
    )
    responsible_doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='responsible_appointments')

    def __str__(self):
        return f"{self.appointment_type} on {self.datetime.strftime('%Y-%m-%d %H:%M')}"


class AppointmentAssignment(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('appointment', 'doctor')

    def __str__(self):
        return f"{self.doctor.full_name} assisting {self.appointment}"
