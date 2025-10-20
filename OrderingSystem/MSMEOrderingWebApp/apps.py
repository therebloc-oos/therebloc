from django.apps import AppConfig

class MSMEOrderingWebAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'MSMEOrderingWebApp'

    def ready(self):
        import MSMEOrderingWebApp.signals
