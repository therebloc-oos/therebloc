from django.shortcuts import redirect
from django.views.decorators.cache import never_cache
from functools import wraps

def login_required_session(allowed_roles=None):
    """
    Decorator to ensure the user is logged in and has the proper role.

    allowed_roles: list of user_type values allowed to access the view.
                   Examples:
                     ['owner']
                     ['customer']
                     ['cashier', 'rider']
    """
    def decorator(view_func):
        @wraps(view_func)
        @never_cache
        def wrapper(request, *args, **kwargs):
            user_type = request.session.get('user_type')

            # Not logged in
            if not user_type:
                return redirect('login')

            # Logged in but not allowed
            if allowed_roles and user_type not in allowed_roles:
                # Optional: redirect to their respective home/dashboard
                if user_type == 'owner':
                    return redirect('dashboard')
                elif user_type == 'cashier':
                    return redirect('cashier_dashboard')
                elif user_type == 'rider':
                    return redirect('deliveryrider_home')
                elif user_type == 'customer':
                    return redirect('customer_home')
                else:
                    return redirect('login')

            # Allowed → proceed
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
