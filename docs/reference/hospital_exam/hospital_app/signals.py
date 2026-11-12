from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
from django.utils.timezone import now
from .models import Appointment, Patient


@receiver(pre_save, sender=Appointment)
def appointment_status_adjustment(sender, instance, **kwargs):
    # If marked as completed but datetime is in the future, revert.
    if instance.status == 'completed' and instance.datetime > now():
        instance.status = 'scheduled'

    # If marked as scheduled but datetime is in the past, flip to completed.
    if instance.status == 'scheduled' and instance.datetime < now():
        instance.status = 'completed'

    # Bonus: if the doctor (as responsible) already has appointments with
    # three or more distinct patients from the same institution as the new
    # patient, attach a "High workload" note.
    if instance.pk is None and instance.patient_id is not None:
        doctor = instance.responsible_doctor
        patient_institution = instance.patient.institution
        patient_ids = (
            Appointment.objects
            .filter(
                responsible_doctor=doctor,
                patient__institution=patient_institution,
            )
            .values_list('patient_id', flat=True)
            .distinct()
        )
        if len(patient_ids) >= 3:
            instance.note = (
                f"High workload with patients from institution "
                f"{patient_institution}."
            )


@receiver(pre_delete, sender=Patient)
def cleanup_appointments_before_patient_deletion(sender, instance, **kwargs):
    # pre_delete is required: by the time post_delete fires Django has
    # already SET_NULL'd / cascaded the related rows, so a query against
    # Appointment.objects.filter(patient=instance) would come back empty.
    for appt in Appointment.objects.filter(patient=instance):
        if appt.status == 'scheduled':
            appt.delete()
        elif appt.status == 'in_progress':
            appt.note = (
                "Patient record missing - appointment preserved for "
                "audit purposes."
            )
            appt.save()
