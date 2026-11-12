from django.apps import AppConfig


class HospitalAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hospital_app'

    def ready(self):
        from . import signals