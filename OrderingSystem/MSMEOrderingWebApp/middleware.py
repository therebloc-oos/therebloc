from django.urls import reverse
from django.shortcuts import redirect
from MSMEOrderingWebApp.models import BusinessDetails, BusinessOwnerAccount
import os
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

class BusinessOwnerSetupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        allowed_paths = [
            reverse('login'),
            reverse('logout'),
            reverse('force_change'),
            reverse('verify_email'),
            reverse('online_payment_details'),
            reverse('upload_logo'),
        ]
        allowed_prefixes = ['/static/', '/media/', '/admin']

        # ✅ Allow static, media, login, logout, and force_change
        if any(request.path.startswith(prefix) for prefix in allowed_prefixes) or request.path in allowed_paths:
            return self.get_response(request)

        owner_id = request.session.get('owner_id')
        if owner_id:
            try:
                owner = BusinessOwnerAccount.objects.get(id=owner_id)

                # ✅ If first_login2 is still True → restrict access
                if owner.first_login2:
                    # Allow access only to settings module
                    if not request.path.startswith(reverse('settings')):
                        return redirect('settings')

            except BusinessOwnerAccount.DoesNotExist:
                pass

        return self.get_response(request)

class EnsureMediaDirectoryMiddleware(MiddlewareMixin):
    """Ensure media directory exists"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Ensure media directories exist
        self.create_media_directories()
        super().__init__(get_response)
    
    def create_media_directories(self):
        """Create media directories if they don't exist"""
        try:
            # Create base media directory
            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
            
            # Create subdirectories
            subdirs = ['product_images', 'business_logos', 'staff_photos']
            for subdir in subdirs:
                dir_path = os.path.join(settings.MEDIA_ROOT, subdir)
                os.makedirs(dir_path, exist_ok=True)
                
            print(f"Media directories created/verified at: {settings.MEDIA_ROOT}")
            
        except Exception as e:
            print(f"Error creating media directories: {e}")

    def process_request(self, request):
        return None
