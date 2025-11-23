from .models import Cart

def cart_count(request):
    """Add cart item count to all templates for logged-in customers"""
    count = 0
    
    # Check if user is a logged-in customer
    if request.session.get('user_type') == 'customer':
        email = request.session.get('email')
        if email:
            count = Cart.objects.filter(email=email).count()
    
    return {'cart_count': count}
