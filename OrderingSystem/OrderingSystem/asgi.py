import os
import django
from django.core.asgi import get_asgi_application

# Set the Django settings module FIRST
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'OrderingSystem.settings')

# Setup Django BEFORE importing anything that uses Django
django.setup()

# Import channels components AFTER django.setup()
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Import your routing AFTER django.setup()
from MSMEOrderingWebApp.routing import websocket_urlpatterns

# Get the Django ASGI application
django_asgi_app = get_asgi_application()

# Configure the ASGI application
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
