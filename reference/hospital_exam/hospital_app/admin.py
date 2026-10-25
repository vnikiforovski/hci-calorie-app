from django.contrib import admin
from django.utils.timezone import now
from .models import Doctor, Patient, Appointment, AppointmentAssignment
from django.db.models import Q

class DoctorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "specialty", "institution", "completed_appointments")

    def has_add_permission(self, request):
        return request.user.is_superuser

class PatientAdmin(admin.ModelAdmin):
    list_display = ("full_name", "birth_date", "gender", "email")

    def has_add_permission(self, request):
        return request.user.is_superuser

class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("appointment_type", "status", "datetime", "patient", "responsible_doctor")

    def has_add_permission(self, request):
        return Doctor.objects.filter(user=request.user).exists() or request.user.is_superuser

    def save_model(self, request, obj, form, change):
        if not change:
            if not obj.responsible_doctor_id:
                doctor = Doctor.objects.filter(user=request.user).first()
                if doctor:
                    obj.responsible_doctor = doctor
        else:
            old_obj = Appointment.objects.get(pk=obj.pk)
            if old_obj.status == 'in_progress' and obj.status == 'completed':
                obj.responsible_doctor.completed_appointments += 1
                obj.responsible_doctor.save()
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj:
            doctor_qs = Doctor.objects.filter(user=request.user)
            if doctor_qs.exists():
                doctor = doctor_qs.first()
                return obj.responsible_doctor == doctor
        return False

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status != 'scheduled':
            return False
        return super().has_delete_permission(request, obj)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        doctor_qs = Doctor.objects.filter(user=request.user)
        if not doctor_qs.exists():
            return qs.none()
        doctor = doctor_qs.first()
        return qs.filter(
            Q(responsible_doctor=doctor) |
            Q(appointmentassignment__doctor=doctor)
        ).distinct()

admin.site.register(Doctor, DoctorAdmin)
admin.site.register(Patient, PatientAdmin)
admin.site.register(Appointment, AppointmentAdmin)
admin.site.register(AppointmentAssignment)
