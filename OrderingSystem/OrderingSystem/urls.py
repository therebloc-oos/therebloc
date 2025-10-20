from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('MSMEOrderingWebApp.urls')),  # ✅ main app at root
]

# ✅ Serve static and media files
if settings.DEBUG:
    # During development
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # Production (Render)
    urlpatterns += [
        # Serve media files from persistent disk
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]

    # Static files should still be served by WhiteNoise in production,
    # so we don’t re-map static here unless needed for debugging.
