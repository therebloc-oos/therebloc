from django.db import models
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.utils import timezone
from django.forms import ValidationError
from django.utils.timezone import now
import uuid

class User(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    contact_number = models.CharField(max_length=15)
    email = models.EmailField(unique=True)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=100)
    zipcode = models.CharField(max_length=10)
    password = models.CharField(max_length=128)
    status = models.CharField(max_length=20, default='not verified')
    verification_token = models.CharField(max_length=64, blank=True, null=True)
    access = models.CharField(max_length=10, choices=[('enabled', 'Enabled'), ('disabled', 'Disabled')], default='enabled')
    role = models.CharField(max_length=10, choices=[('user', 'User'), ('cashier', 'Cashier')], default='user')  # Role field added
    image = models.ImageField(upload_to='user_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class StaffAccount(models.Model):
    ROLE_CHOICES = [
        ('cashier', 'Cashier'),
        ('rider', 'Delivery Rider'),
    ]
    ACCESS_CHOICES = [
        ('enabled', 'Enabled'),
        ('disabled', 'Disabled'),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    contact_number = models.CharField(max_length=15)
    password = models.CharField(max_length=128)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='cashier')
    access = models.CharField(max_length=10, choices=ACCESS_CHOICES, default='enabled')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='not verified')  # "verified" or "not verified"
    verification_token = models.CharField(max_length=64, blank=True, null=True)  # stores unique token
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.role}"
    
class ProductCategory(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.title()
        super().save(*args, **kwargs)
    
class Products(models.Model):
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='product_images/', null=True, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True) 
    variation_name = models.CharField(max_length=100, default='Default')  
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stocks = models.PositiveIntegerField(default=0)
    track_stocks = models.BooleanField(default=True)
    available = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)  
    last_updated = models.DateTimeField(auto_now=True)
    sold_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} - {self.variation_name}"
    
    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.title()
        if self.variation_name:
            self.variation_name = self.variation_name.title()
        super().save(*args, **kwargs)

class ArchivedProducts(models.Model):
    original_id = models.IntegerField()  # track original product ID
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    variation_name = models.CharField(max_length=100, default='Default')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stocks = models.PositiveIntegerField(default=0)
    sold_count = models.PositiveIntegerField(default=0)
    archived_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Archived: {self.name} - {self.variation_name}"

class ProductEditHistory(models.Model):
    product = models.ForeignKey(Products, on_delete=models.CASCADE, related_name="edit_history")
    field = models.CharField(max_length=50)  # "price" or "stocks"
    old_value = models.CharField(max_length=100, null=True, blank=True)
    new_value = models.CharField(max_length=100, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} - {self.field} changed from {self.old_value} to {self.new_value}"

class OnlinePaymentDetails(models.Model):
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    qr_image = models.ImageField(upload_to='qr_codes/', max_length=255, null=True, blank=True)
    recipient_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.bank_name} - {self.recipient_name}"

class BusinessOwnerAccount(models.Model):
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)  # Storing plain text password (NOT recommended in production)
    first_login = models.BooleanField(default=True)
    first_login2 = models.BooleanField(default=True)
    status = models.CharField(max_length=20, default='not verified')  
    verification_token = models.CharField(max_length=64, blank=True, null=True)  

    def __str__(self):
        return self.email

@receiver(post_migrate)
def create_default_business_owner(sender, **kwargs):
    if sender.name == 'MSMEOrderingWebApp':  # Replace YOUR_APP_NAME with your Django app's name
        BusinessOwnerAccount.objects.get_or_create(
            email='businessowner@gmail.com',
            defaults={
                'password': 'msme2025!',
                'first_login': True
            }
        )

class BusinessDetails(models.Model):
    business_name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='business_logos/', null=True, blank=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    email_address = models.EmailField(max_length=255, blank=True, null=True)
    store_address = models.TextField(blank=True, null=True)

    business_description = models.TextField(blank=True, null=True)
    business_mission = models.TextField(blank=True, null=True)
    business_vision = models.TextField(blank=True, null=True)

    start_day = models.CharField(max_length=20, blank=True, null=True)
    end_day = models.CharField(max_length=20, blank=True, null=True)
    opening_time = models.TimeField(blank=True, null=True)
    closing_time = models.TimeField(blank=True, null=True)
    force_closed = models.BooleanField(default=False)

    services_offered = models.JSONField(default=list, blank=True)
    payment_methods = models.JSONField(default=list, blank=True)

    specific_onsite_service = models.TextField(blank=True, null=True)
    # Delivery fee settings
    base_fare = models.FloatField(default=50.0)
    additional_fare_per_km = models.FloatField(default=10.0)

    def __str__(self):
        return self.business_name

    def calculate_delivery_fee(self, distance_km):
        """
        Calculates delivery fee: base fare + (additional fare * km over 1)
        """
        if distance_km <= 1:
            return self.base_fare
        else:
            extra_km = distance_km - 1
            return self.base_fare + (extra_km * self.additional_fare_per_km)

class SocialMedia(models.Model):
    business = models.ForeignKey("BusinessDetails", on_delete=models.CASCADE, related_name="social_media")
    platform = models.CharField(max_length=100)
    username_or_link = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.business.business_name} - {self.platform}"
        
class Cart(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=15)
    address = models.TextField()
    email = models.EmailField()
    image = models.ImageField(null=True, blank=True)
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.product_name}"

class PlacedOrder(models.Model):
    ORDER_TYPE_CHOICES = [
        ('pickup', 'Pickup'),
        ('delivery', 'Home Delivery'),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=15)
    address = models.TextField()
    email = models.EmailField()
    image = models.ImageField(null=True, blank=True)
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    order_type = models.CharField(max_length=10, choices=ORDER_TYPE_CHOICES)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.product_name} ({self.order_type})"
    
class Checkout(models.Model):
    # Customer info
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=15)
    address = models.TextField()
    email = models.EmailField()

    # Product info
    image = models.ImageField(null=True, blank=True)  # product image
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # total for this item

    # Checkout-specific fields
    sub_total = models.DecimalField(max_digits=10, decimal_places=2)
    order_type = models.CharField(max_length=255)  # e.g., "Delivery" or "Pickup"
    specific_order_type = models.CharField(max_length=255, null=True, blank=True)
    payment_method = models.CharField(max_length=50)  # e.g., "COD", "GCash", "Bank Transfer"
    proof_of_payment = models.ImageField(upload_to='proofs/', null=True, blank=True)
    additional_notes = models.TextField(blank=True)
    order_code = models.CharField(max_length=10, null=True)
    created_at = models.DateTimeField(default=now, editable=False, null=True)
    is_seen_by_owner = models.BooleanField(default=False)
    is_seen_by_customer = models.BooleanField(default=False)
    
      # Status field
    status = models.CharField(max_length=50, default='pending')
    delivery_method = models.CharField(max_length=50, null=True, blank=True)  # e.g., in_house or third_party
    tracking_url = models.URLField(null=True, blank=True)
    eta_value = models.PositiveIntegerField(null=True, blank=True)  # numeric ETA value
    eta_unit = models.CharField(
        max_length=10,
        choices=[
            ('minutes', 'Minutes'),
            ('hours', 'Hours'),
            ('days', 'Days'),
            ('weeks', 'Weeks'),
        ],
        null=True,
        blank=True
    )
    rider = models.CharField(max_length=150, null=True, blank=True)
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    proof_of_delivery = models.ImageField(upload_to='delivery_proofs/', null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)  # <--- NEW

    cash_given = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    change = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    group_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    void_reason = models.CharField(
        max_length=50,
        choices=[
            ('unclaimed', 'Unclaimed'),
            ('canceled', 'Canceled'),
            ('returned', 'Returned'),
            ('other', 'Other'),
        ],
        null=True,
        blank=True
    )
    
    def save(self, *args, **kwargs):
        # If the object already exists, check if status changed
        if self.pk:
            old = Checkout.objects.filter(pk=self.pk).first()
            if old and old.status != self.status:
                self.updated_at = timezone.now()
        else:
            # For new objects, make sure updated_at is set initially
            self.updated_at = timezone.now()
            
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"Order by {self.first_name} {self.last_name} - {self.product_name}"    
    
class CustomerReview(models.Model):
    # If you want reviews to survive user deletion, switch to SET_NULL. If you're fine with deleting reviews
    # when a user is deleted, keep CASCADE.
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # Make these optional to avoid duplication for logged-in users
    name = models.CharField(max_length=100, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    contact_number = models.CharField(max_length=15, blank=True, default="")

    rating = models.PositiveIntegerField(default=5)
    review = models.TextField()
    submitted_at = models.DateTimeField(default=timezone.now)
    owner_response = models.TextField(blank=True, null=True)
    response_date = models.DateTimeField(null=True, blank=True)
    is_hidden = models.BooleanField(default=False)
    anonymous = models.BooleanField(default=False)

    def __str__(self):
        who = "Anonymous" if self.anonymous else (
            f"{self.user.first_name} {self.user.last_name}" if self.user else (self.name or "Customer")
        )
        return f"Review by {who}"
    
class ReviewPhoto(models.Model):
    review = models.ForeignKey(CustomerReview, related_name='photos', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='review_photos/')

    def __str__(self):
        return f"Photo for review {self.review.id}"


class OTP(models.Model):
    email = models.EmailField(unique=True)  # Email field to associate with the OTP
    otp = models.CharField(max_length=6)  # OTP will be a 6-digit number, so max length is 6
    created_at = models.DateTimeField(auto_now_add=True)  # To track when the OTP was created

    def __str__(self):
        return f"OTP for {self.email}: {self.otp}"
    
    def clean(self):
        # Ensure OTP is numeric
        if not self.otp.isdigit():
            raise ValidationError("OTP must only contain numbers.")
        if len(self.otp) != 6:  # Ensuring OTP is 6 digits
            raise ValidationError("OTP must be exactly 6 digits.")

#sample customize

class Customization(models.Model):
    # General Background Settings (Shared by all modules)
    general_background_type = models.CharField(max_length=20, default='solid')
    general_solid_color = models.CharField(max_length=7, default='#ffffff')
    general_gradient_color_1 = models.CharField(max_length=7, default='#ffffff')
    general_gradient_color_2 = models.CharField(max_length=7, default='#000000')
    general_gradient_color_3 = models.CharField(max_length=7, null=True, blank=True)
    general_gradient_direction = models.CharField(max_length=20, default='to right')
    general_radial_shape = models.CharField(max_length=20, null=True, blank=True)
    general_radial_position = models.CharField(max_length=20, null=True, blank=True)
    general_background_image = models.ImageField(upload_to='backgrounds/', null=True, blank=True)

    # Login-specific Background Settings
    login_background_type = models.CharField(max_length=20, default='solid')
    login_solid_color = models.CharField(max_length=7, default='#ffffff')
    login_gradient_color_1 = models.CharField(max_length=7, default='#ffffff')
    login_gradient_color_2 = models.CharField(max_length=7, default='#000000')
    login_gradient_color_3 = models.CharField(max_length=7, null=True, blank=True)
    login_gradient_direction = models.CharField(max_length=20, default='to right')
    login_radial_shape = models.CharField(max_length=20, null=True, blank=True)
    login_radial_position = models.CharField(max_length=20, null=True, blank=True)
    login_background_image = models.ImageField(upload_to='backgrounds/', null=True, blank=True)

    # Register-specific Background Settings
    register_background_type = models.CharField(max_length=20, default='solid')
    register_solid_color = models.CharField(max_length=7, default='#ffffff')
    register_gradient_color_1 = models.CharField(max_length=7, default='#ffffff')
    register_gradient_color_2 = models.CharField(max_length=7, default='#000000')
    register_gradient_color_3 = models.CharField(max_length=7, null=True, blank=True)
    register_gradient_direction = models.CharField(max_length=20, default='to right')
    register_radial_shape = models.CharField(max_length=20, null=True, blank=True)
    register_radial_position = models.CharField(max_length=20, null=True, blank=True)
    register_background_image = models.ImageField(upload_to='backgrounds/', null=True, blank=True)

    # Font Settings (Shared by all modules)
    header_font_family = models.CharField(max_length=50, default='Arial')
    header_font_size = models.IntegerField(default=24)
    header_font_color = models.CharField(max_length=7, default='#000000')
    header_font_style = models.CharField(max_length=20, default='normal')
    
    body_font_family = models.CharField(max_length=50, default='Arial')
    body_font_size = models.IntegerField(default=14)
    body_font_color = models.CharField(max_length=7, default='#000000')

    # Navigation-specific Background Settings
    navigation_background_type = models.CharField(max_length=20, default='solid')
    navigation_solid_color = models.CharField(max_length=7, default='#ffffff')
    navigation_gradient_color_1 = models.CharField(max_length=7, default='#ffffff')
    navigation_gradient_color_2 = models.CharField(max_length=7, default='#000000')
    navigation_gradient_color_3 = models.CharField(max_length=7, null=True, blank=True)
    navigation_gradient_direction = models.CharField(max_length=20, default='to right')
    navigation_radial_shape = models.CharField(max_length=20, null=True, blank=True)
    navigation_radial_position = models.CharField(max_length=20, null=True, blank=True)

    # Navigation Text, Hover, and Border Color Settings
    navigation_text_color = models.CharField(max_length=7, default='#000000')
    navigation_hover_color = models.CharField(max_length=7, default='#a8a8a8')
    navigation_border_color = models.CharField(max_length=7, default='#cccccc')

    # New Fields Added
    input_rounded_corner = models.IntegerField(default=1)  # Rounding of input corners
    primary_color = models.CharField(max_length=7, default='#000000')  # Primary color
    secondary_color = models.CharField(max_length=7, default="#1F1F1F")  # Secondary color
    accent_color = models.CharField(max_length=7, default="#6D6D6D")  # Accent color
    button_rounded_corner = models.IntegerField(default=1)  # Rounding of button corners
    button_text_color = models.CharField(max_length=7, default='#ffffff')
    input_border_width = models.IntegerField(default=1)
    input_border_style = models.CharField(max_length=20, default='solid')

    # models.py

    homepage_image_1 = models.ImageField(upload_to='homepage/', null=True, blank=True)
    homepage_image_2 = models.ImageField(upload_to='homepage/', null=True, blank=True)
    homepage_image_3 = models.ImageField(upload_to='homepage/', null=True, blank=True)
    homepage_image_4 = models.ImageField(upload_to='homepage/', null=True, blank=True)
    homepage_image_5 = models.ImageField(upload_to='homepage/', null=True, blank=True)

    show_best_sellers = models.BooleanField(default=True)
    best_sellers_title = models.CharField(max_length=100, default='Best Sellers')
    best_sellers_description = models.TextField(default="Our most popular products loved by customers.")
    dynamic_description = models.TextField(default="Shop with us today and find what you love!")



    def __str__(self):
        return f"Customization Settings - {self.id}"
