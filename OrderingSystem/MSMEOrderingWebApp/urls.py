from django.urls import path
from . import views

urlpatterns = [
    path('Login/', views.login_view, name='login'),
    path('Logout/', views.logout_view, name='logout'),
    path('UserRegistration/', views.register_user, name='register_user'),

    path('BusinessDashboard/', views.dashboard, name='dashboard'),
    path('ManageInventory/', views.inventory, name='inventory'),

    path('Point-of-Sale/', views.pos, name='pos'),
    path('Point-of-Sale/Cart/', views.pos_cart_view, name='pos_cart'),

    path('Delivery/', views.delivery, name='delivery'),
    path('Reviews/', views.reviews, name='reviews'),
    path('RegisteredUsers/', views.users, name='users'),
    path('enable_user/<str:role>/<int:user_id>/', views.enable_user, name='enable_user'),
    path('disable_user/<str:role>/<int:user_id>/', views.disable_user, name='disable_user'),

    path('Settings/', views.business_settings, name='settings'),
    path('Settings/', views.settings, name='settings'),
    path('settings/online-payment/', views.online_payment_details, name='online_payment_details'),
    path('delete-payment/<int:id>/', views.delete_online_payment, name='delete_online_payment'),
    path('Settings/change-password/', views.business_changepassword, name='business_changepassword'),

    path('BusinessNotifications/', views.business_notifications, name='business_notifications'),

    path('CustomerHomepage/', views.customer_home, name='customer_home'),
    path('CustomerReviews/', views.customer_reviews, name='customer_reviews'),
    path('CustomerCart/', views.customer_cart, name='customer_cart'),
    path('delete-cart-item/<int:cart_id>/', views.delete_cart_item, name='delete_cart_item'),
    path('CustomerCheckout/', views.customer_checkout, name='customer_checkout'),
    path('customer/online-payment/', views.customer_viewonlinepayment, name='customer_viewonlinepayment'),
    path('business/online-payment/', views.business_viewonlinepayment, name='business_viewonlinepayment'),
    path('cashier/online-payment/', views.cashier_viewonlinepayment, name='cashier_viewonlinepayment'),
    path('CustomerNotifications/', views.customer_notifications, name='customer_notifications'),
    path('CustomerProfile/', views.customer_profile, name='customer_profile'),
    path('CustomerProfile/change-password/', views.customer_changepassword, name='customer_changepassword'),

    path('delete-product/<int:product_id>/', views.delete_product, name='delete_product'),
    path('edit-price/', views.edit_product_price, name='edit_product_price'),
    path('toggle-availability/<int:product_id>/', views.toggle_availability, name='toggle_availability'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('MSMEOrderingWebApp/forcechange/', views.force_change, name='force_change'),
    path('add-to-cart/', views.add_to_cart, name='add_to_cart'),
    path('update-cart/<int:cart_id>/', views.update_cart, name='update_cart'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('forgot-password_otp/', views.forgot_passwordotp, name='forgot_passwordotp'),
    path('forgot-password_reset/', views.forgot_password_reset, name='forgot_password_reset'),
    path('save_customization/', views.customization_settings, name='save_customization'),
    path('update-review-response/<int:review_id>/', views.update_review_response, name='update_review_response'),
    path('hide-review/<int:review_id>/', views.hide_review, name='hide_review'),
    path('show-review/<int:review_id>/', views.show_review, name='show_review'),
    path('customer-reviews/', views.customer_reviews, name='customer_reviews'),
    path('reviews/', views.customer_reviews, name='reviews_page'), 
    path('pos/update-cart-quantity/', views.update_pos_cart_quantity, name='update_pos_cart_quantity'),
    path('pos/add-to-cart/', views.pos_add_to_cart, name='pos_add_to_cart'),
    path('pos/remove-cart-item/<int:item_id>/', views.remove_cart_item, name='remove_cart_item'),
    path('pos/clear-cart/', views.clear_cart_items, name='clear_cart_items'),
    path('pos-add-to-cart-variation/', views.pos_add_to_cart_variation, name='pos_add_to_cart_variation'),
    path('pos/place-order/', views.pos_place_order, name='pos_place_order'),
    path('business/pending-orders/', views.partial_pending_orders, name='partial_pending_orders'),
    path('partial/pending-orders/', views.partial_pending_orders, name='partial_pending_orders'),
    path('partial/customer-notifications/', views.partial_customer_notifications, name='partial_customer_notifications'),
    path('update-order-status/', views.update_order_status, name='update_order_status'),
    path('partial/customer-notifications/', views.partial_customer_notifications, name='partial_customer_notifications'),
    path('notifications/', views.notifications_redirect, name='notifications'),

    path('update-order-status-progress/', views.update_order_status_progress, name='update_order_status_progress'),
    path('create-staff-account/', views.create_staff_account, name='create_staff_account'),
    path('deliveryrider/home/', views.deliveryrider_home, name='deliveryrider_home'),
    path('mark-as-delivered/', views.mark_as_delivered, name='mark_as_delivered'),
    path('', views.route_home, name='home'),

    path('cashier/home/', views.cashier_pos, name='cashier_pos'),
    path('Cashier/Point-of-Sale/Cart/', views.cashier_pos_cart_view, name='cashier_poscart'),
    path('Cashier/Dashboard/', views.cashier_dashboard, name='cashier_dashboard'),
    path('Cashier/Notifications/', views.cashier_notifications, name='cashier_notifications'),
    path('Cashier/Delivery/', views.cashier_delivery, name='cashier_delivery'),

    path('owner/change-password/', views.change_owner_password, name='owner_changepassword'),
    path('staff/profile/', views.staff_profile, name='staff_profile'),
    path('reject-order/<str:order_code>/', views.reject_order, name="reject_order"),

    path("reports/sales/", views.sales_report_pdf, name="sales_report_pdf"),

    path('reset_customization/', views.reset_customization, name='reset_customization'),
    path("upload-logo/", views.upload_logo, name="upload_logo"),
    path("toggle-shop-status/", views.toggle_shop_status, name="toggle_shop_status"),
]

