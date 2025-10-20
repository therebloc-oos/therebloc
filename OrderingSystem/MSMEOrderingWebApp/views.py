from django.shortcuts import render, redirect, get_object_or_404
from .models import OTP, BusinessOwnerAccount, User, Products, ProductCategory, OnlinePaymentDetails, BusinessDetails, StaffAccount, ArchivedProducts, ProductEditHistory, SocialMedia
from django.contrib import messages
from django.db.models import Min, Max
from collections import defaultdict
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.core import serializers
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.utils.http import urlencode
from secrets import token_urlsafe
from urllib.parse import urlencode
from .decorators import login_required_session
from django.http import JsonResponse
from .models import Cart, Checkout
import json
import re
from django.views.decorators.csrf import csrf_exempt
from .models import CustomerReview
from django.utils import timezone
from django.views.decorators.http import require_POST
import random
from django.utils.timezone import localtime, now, make_aware, get_current_timezone
from .models import Customization
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from datetime import time
from django.utils.timezone import make_aware, now
from datetime import datetime, timedelta, time, date
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from .utils import get_or_create_customization
from django.utils.timezone import make_aware, localtime, get_current_timezone
from django.shortcuts import redirect
from django.urls import resolve, reverse
from escpos.printer import Usb
from .utils import get_business_day_range
import uuid
import os
from django.utils.timezone import make_aware
from datetime import datetime, timedelta
import io
from collections import defaultdict
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from django.utils.timezone import localdate
from django.db.models import F
from django.core.mail import EmailMultiAlternatives
from django.conf import settings as django_settings
from django.contrib.auth.hashers import make_password

@csrf_exempt
def toggle_shop_status(request):
    business = BusinessDetails.objects.first()  # adjust if multi-business

    if request.method == "POST":
        # Toggle forced closed
        business.force_closed = not business.force_closed
        business.save()
        return JsonResponse({"force_closed": business.force_closed})

    elif request.method == "GET":
        # Return current force_closed status
        return JsonResponse({"force_closed": business.force_closed})

    return JsonResponse({"error": "Invalid request"}, status=400)


def route_home(request):
    user_type = request.session.get('user_type')

    if user_type == 'owner':
        owner_id = request.session.get('owner_id')
        try:
            owner = BusinessOwnerAccount.objects.get(id=owner_id)
            if owner.first_login2:
                return redirect('settings')
            return redirect('dashboard')
        except BusinessOwnerAccount.DoesNotExist:
            pass

    elif user_type == 'customer':
        return redirect('customer_home')

    elif user_type == 'rider':
        return redirect('deliveryrider_home')

    # ⬅️ If not logged in, show login page
    return redirect('login')

def print_receipt(order, orders):
    try:
        p = Usb(0x0483, 0x5840, timeout=0, in_ep=0x82, out_ep=0x04)
        p.set(align='center', bold=True, width=2, height=2)
        p.text("Receipt\n\n")
        p.set(align='left', bold=False, width=1, height=1)
        p.text(f"Order Code: {order.order_code}\n")
        p.text(f"Customer: {order.first_name} {order.last_name}\n")
        p.text(f"Phone: {order.contact_number}\n")
        p.text(f"Address: {order.address}\n\n")

        # Products
        total = 0
        for item in orders:
            line = f"{item.product_name} (x{item.quantity}) - ₱{item.price:.2f}\n"
            total += item.price
            p.text(line)

        # Footer
        p.text(f"\nTotal: ₱{total:.2f}\n")
        p.text(f"Payment: {order.payment_method}\n")
        p.text(f"Date: {order.created_at.strftime('%Y-%m-%d %H:%M')}\n\n")
        p.text("Thank you!\n\n")
        p.cut()
    except Exception as e:
        print("Failed to print receipt:", e)

def notifications_redirect(request):
    user_type = request.session.get('user_type')

    if user_type == 'owner':
        return redirect('business_notifications')
    elif user_type == 'customer':
        return redirect('customer_notifications')
    elif user_type == 'staff':
        staff_id = request.session.get('staff_id')
        try:
            staff = StaffAccount.objects.get(id=staff_id)
            if staff.role == 'cashier':
                return redirect('cashier_notifications')
            else:
                messages.warning(request, "This staff role has no notifications page.")
                return redirect('login')  # or redirect somewhere else
        except StaffAccount.DoesNotExist:
            messages.error(request, "Staff account not found.")
            return redirect('login')
    else:
        return redirect('login')  # fallback if session is missing or unknown
    
def send_order_status_email(recipient_email, order_code, status, orders, rejection_reason=None, void_reason=None):
    # Get customization settings
    customization = get_or_create_customization()
    business = BusinessDetails.objects.first()

    # Prepare subject
    subject = f"Your order has been {status.capitalize()}"

    # Generate item lines dynamically from the passed 'orders' list
    item_lines = []
    total_price = sum(order.price for order in orders)
    item_list = "\n".join([f"<tr><td style='padding: 10px; text-align: left;'>{order.product_name} (x{order.quantity})</td><td style='padding: 10px; text-align: right;'>₱{order.price:.2f}</td></tr>" for order in orders])

    # Message Content Based on Status
    message_content = ""
    if status.lower() == "rejected":
        message_content = f"""
        <p style="font-size: 14px; color: #d9534f; margin: 0;">We're sorry, but your order has been REJECTED.</p>
        <p style="font-size: 16px; color: #8B0000; font-weight: bold; line-height: 1.6;">Reason for rejection: <span style="font-size: 16px; color: #888;">{rejection_reason}</span></p>
        <p style="font-size: 14px; color: #333; margin-top: 2 px;">Please review your order details, correct any errors, and try submitting a new order.</p>
        """
    elif status.lower() == "accepted":
        message_content = f"""
        <p style="padding-left: 20px; padding-right:20px; font-size: 15px; color: #555; font-weight: bold; line-height: 1.6;">Good news! Your order has been ACCEPTED and is being PROCESSED.</p>
        <p style="padding-left: 20px; padding-right:20px; font-size: 13px; color: #555; margin-top: 2px;">We are working to get your order ready for shipment. Stay tuned for updates.</p>
        """
    elif status == "Preparing":
        message_content = f"""
        <p style="padding-left: 20px; padding-right:20px; font-size: 15px; color: #555; font-weight: bold; line-height: 1.6;">Your order is now being PREPARED!</p>
        <p style="padding-left: 20px; padding-right:20px; font-size: 13px; color: #555; margin-top: 2px;">We are preparing your orders and getting them ready for packing.</p>
        """
    elif status == "Packed":
        message_content = f"""
        <p style="padding-left: 20px; padding-right:20px; font-size: 15px; color: #555; font-weight: bold; line-height: 1.6;">Your order has been PACKED!</p>
        """
    elif status == "Ready for Pickup":
        message_content = f"""
        <p style="padding-left: 20px; padding-right:20px; font-size: 15px; color: #555; font-weight: bold; line-height: 1.6;">Your order is now READY FOR PICK UP!</p>
        <p style="padding-left: 20px; padding-right:20px; font-size: 15px; color: #555; margin-top: 10px;">Please show this email including your order code.</p>
        """
    elif status == "Out for Delivery":
        message_content = f"""
        <p style="font-size: 15px; color: #008000; font-weight: bold; line-height: 1.6;">Your order is now OUT FOR DELIVERY!</p>
        <p style="padding-left: 20px; padding-right:20px; font-size: 14px; color: #333; margin-top: 10px;">Your order is on its way and should reach you soon! If you have any questions, feel free to reach out.</p>
        """
    elif status == "Completed":
        message_content = f"""
        <p style="font-size: 15px; color: #008000; font-weight: bold; line-height: 1.6;">Your order has been successfully COMPLETED!</p>
        <p style="font-size: 13px; color: #333; margin-top: 10px;">Thank you for shopping with us. We hope you love your purchase! Please feel free to reach out for any future needs.</p>
        """
    elif status == "Void":
        message_content = f"""
        <p style="font-size: 15px; color: #8B0000; font-weight: bold; line-height: 1.6;">
            Your order has been voided.
        </p>
        <p style="font-size: 13px; color: #555; margin-top: 10px;">
            Reason: <span style="color: #333;">{void_reason if void_reason else "No reason specified"}</span>
        </p>
        <p style="font-size: 13px; color: #555; margin-top: 10px;">
            If you have questions, please contact us for assistance.
        </p>
        """
    else:
        message_content = f"""
        <p style="font-size: 15px; color: #333; line-height: 1.6;">Your order status is now {status}.</p>
        <p style="font-size: 13px; color: #333; margin-top: 10px;">We will notify you once there are any changes or updates regarding your order.</p>
        """

    # Build the body of the email
    body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 0; color: #333;">
            <div style="width: 100%; height: 100%; padding: 40px 0;">
                <table align="center" width="700" style="border-collapse: collapse; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08); margin: 0 auto;">
                    
                    <!-- Header -->
                    <tr>
                        <td align="center" style="padding: 25px; background: linear-gradient(135deg, {customization.primary_color} 100%, {customization.secondary_color} 100%); border-top-left-radius: 12px; border-top-right-radius: 12px;">
                            
                            <!-- Business Name (smaller font) -->
                            <p style="font-size: 14px; font-weight: 600; color: {customization.button_text_color}; margin: 0 0 1px 0;">
                                {business.business_name}
                            </p>

                            <!-- Main Title -->
                            <h1 style="font-size: 35px; font-weight: 800; color: {customization.button_text_color}; margin: 0;">
                                ORDER UPDATE
                            </h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 25px; text-align: center; font-size: 18px; line-height: 1.6; color: #555;">
                            
                            <!-- Highlighted Order Code -->
                            <div style="
                                display: inline-block;
                                background-color: {customization.primary_color};
                                color: {customization.button_text_color};
                                font-weight: 800;
                                font-size: 25px;
                                padding: 10px 25px;
                                border-radius: 8px;
                                letter-spacing: 1px;
                                box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
                                margin-top: -10px;
                                margin-bottom: 15px;
                            ">
                                {order_code}
                            </div>

                            <!-- Dynamic Message -->
                            <div class="message" style="font-size: 16px; color: #333; margin-bottom: 20px; line-height: 1.6; text-align: center;">
                                {message_content}
                            </div>

                            <!-- Receipt Section -->
                            <div class="receipt" style="
                                text-align: left; 
                                background: #fafafa; 
                                padding: 15px; 
                                border-radius: 10px; 
                                border: 1px solid #eee; 
                                box-shadow: 0 2px 8px rgba(0,0,0,0.05); 
                                max-width: 580px; 
                                margin: 0 auto; 
                                font-family: 'Courier New', monospace;
                            ">
                                <h3 style="font-size: 18px; font-weight: 800; text-align: center; margin-bottom: 8px;">🧾 Order Summary</h3>
                                <hr style="border: none; border-top: 1px dashed rgba(0,0,0,0.3); margin: 5px 0;">
                                <table width="100%" font-weight:700;  style="border-collapse: collapse; font-size: 14px;">
                                    <thead>
                                        <tr>
                                            <th align="left" style="padding-bottom: 6px;">Item</th>
                                            <th align="right" style="padding-bottom: 6px;">Price</th>
                                        </tr>
                                    </thead>
                                    <tbody style="font-weight:700;">{item_list}</tbody>
                                </table>
                                <hr style="border: none; border-top: 1px dashed rgba(0,0,0,0.3); margin: 10px 0;">
                                <p style="text-align: right; font-weight: 900; font-size: 15px;">Total: ₱{total_price:.2f}</p>
                            </div>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                    <td style="padding: 20px; background-color: #f5f5f5; text-align: center; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px;">
                            <table role="presentation" align="center" cellspacing="0" cellpadding="0" border="0" width="100%" style="text-align: center;">
                                <tr>
                                    <td style="color: {customization.button_text_color}; font-size: 13px; line-height: 1.8; padding: 0 15px;">
                                        <p style="margin: 5px 0;">
                                            <strong>✉️ Email:</strong>
                                            <a href="mailto:{business.email_address}" style="color: {customization.button_text_color}; text-decoration: none; margin-left: 5px;">
                                                {business.email_address}
                                            </a>
                                        </p>
                                        <p style="margin: 5px 0;">
                                            <strong>📞 Contact:</strong> {business.contact_number}
                                        </p>
                                        <p style="margin: 5px 0;">
                                            <strong>📍 Address:</strong> {business.store_address}
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </div>
        </body>
    </html>
    """

    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body="This is an HTML email. Please use an HTML-compatible client.",
            from_email=django_settings.EMAIL_HOST_USER,
            to=[recipient_email],
        )
        email.attach_alternative(body, "text/html")
        email.send()
        print(f"✅ Email sent to {recipient_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")


@csrf_exempt
def update_order_status(request):
    if request.method == "POST":
        data = json.loads(request.body)
        order_code = data.get("order_code")
        status = data.get("status")
        group_id = data.get("group_id")  # Assuming this is sent from frontend

        if not order_code or not status or not group_id:
            return JsonResponse({"success": False, "error": "Missing data"})

        # Filter orders based on order_code and group_id
        orders = Checkout.objects.filter(order_code=order_code, group_id=group_id)

        if not orders.exists():
            return JsonResponse({"success": False, "error": "Order not found"})

        # Restrict "accepted" update to only pending orders
        if status == "accepted":
            orders = orders.filter(status="pending")
            if not orders.exists():
                return JsonResponse({"success": False, "error": "No pending orders to accept"})

        reference_order = orders.first()
        customer_email = reference_order.email

        # Update status for all matching orders
        for order in orders:
            order.status = status
            order.save()

        # Send email to customer
        send_order_status_email(customer_email, order_code, status, orders, void_reason=None)

        channel_layer = get_channel_layer()

        if status == "accepted":
            # Fetch business details
            business = BusinessDetails.objects.first()
            business_name = business.business_name if business else ""
            store_address = business.store_address if business else ""

            # Prepare print data
            print_data = {
                "type": "print",
                "order": {
                    "order_code": reference_order.order_code,
                    "first_name": reference_order.first_name,
                    "last_name": reference_order.last_name,
                    "contact_number": reference_order.contact_number,
                    "address": reference_order.address,
                    "payment_method": reference_order.payment_method,
                    "created_at": timezone.localtime(reference_order.created_at).strftime('%Y-%m-%d %H:%M'),
                    "business_name": business_name,
                    "store_address": store_address,
                    "order_type": reference_order.order_type,
                    "notes": reference_order.additional_notes or ""
                },
                "items": [
                    {
                        "product_name": o.product_name,
                        "quantity": o.quantity,
                        "price": float(o.price),
                    } for o in orders
                ]
            }

            # Add delivery_fee if applicable
            if reference_order.order_type == "delivery" and reference_order.delivery_fee:
                print_data["order"]["delivery_fee"] = float(reference_order.delivery_fee)

			# Send to printer group
            async_to_sync(channel_layer.group_send)(
                "printers",
                {
                    "type": "send_print_job",
                    "data": print_data
                }
            )

            # Deduct stock quantities and update sold_count (grouped by base product name)
            product_sales = defaultdict(int)  # Track total sales per base product

            for order in orders:
                raw_name = order.product_name.strip()

                try:
                    product_name, variation_name = [part.strip() for part in raw_name.split(" - ", 1)]
                except ValueError:
                    product_name = raw_name
                    variation_name = "Default"

                try:
                    product = Products.objects.get(
                        name__iexact=product_name,
                        variation_name__iexact=variation_name
                    )
                    # ✅ Deduct stocks for this variation
                    if product.track_stocks:
                        product.stocks = max(0, product.stocks - order.quantity)
                    product.save()

                    # ✅ Accumulate sales for the base product
                    product_sales[product_name.lower()] += order.quantity

                except Products.DoesNotExist:
                    print(f"❌ Product not found for: {product_name} - {variation_name}")
                except Products.MultipleObjectsReturned:
                    print(f"⚠️ Multiple products found for: {product_name} - {variation_name}")
                    product = Products.objects.filter(
                        name__iexact=product_name,
                        variation_name__iexact=variation_name
                    ).first()
                    if product:
                        if product.track_stocks:
                            product.stocks = max(0, product.stocks - order.quantity)
                        product.save()
                        product_sales[product_name.lower()] += order.quantity

            # ✅ Update sold_count per base product (sum across variations)
            for base_name, qty in product_sales.items():
                Products.objects.filter(name__iexact=base_name).update(
                    sold_count=F('sold_count') + qty
                )

        # WebSocket: Customer side
        sanitized_email = customer_email.replace("@", "at").replace(".", "_")
        group_name = f"customer_{sanitized_email}"
        customer_count = Checkout.objects.filter(
            email=customer_email, status__in=["accepted", "rejected"]
        ).values("order_code").distinct().count()

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "send_customer_notification",
                "message": f"Your order has been {status}.",
                "customer_count": customer_count,
            }
        )

        # WebSocket: Business owner side
        pending_count = Checkout.objects.filter(status="pending", is_seen_by_owner=False).count()
        async_to_sync(channel_layer.group_send)(
            "notifications",
            {
                "type": "send_pending_count",
                "count": pending_count
            }
        )

        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "error": "Invalid request"})

def send_email_notification(recipient_email, status, order_code, orders, rejection_reason=None, void_reason=None):
    # Get customization and business info
    customization = get_or_create_customization()
    business = BusinessDetails.objects.first()

    # Prepare subject
    subject = f"Your order has been {status.capitalize()}"

    # ✅ Correct total price computation
    total_price = sum(order.price for order in orders)

    # Generate item rows
    item_lines = [
        f"<tr><td style='padding: 10px; text-align: left;'>{order.product_name} (x{order.quantity})</td>"
        f"<td style='padding: 10px; text-align: right;'>₱{order.price:.2f}</td></tr>"
        for order in orders
    ]
    item_list = "\n".join(item_lines)

    # Message Content Based on Status
    message_content = ""
    if status.lower() == "rejected":
        message_content = f"""
        <p style="font-size: 14px; color: #d9534f; margin: 0;">We're sorry, but your order has been REJECTED.</p>
        <p style="font-size: 16px; color: #8B0000; font-weight: bold; line-height: 1.6;">Reason for rejection: <span style="font-size: 16px; color: #888;">{rejection_reason}</span></p>
        <p style="font-size: 14px; color: #333; margin-top: 2 px;">Please review your order details, correct any errors, and try submitting a new order.</p>
        """
    elif status.lower() == "accepted":
        message_content = f"""
        <p style="padding-left: 20px; padding-right:20px; font-size: 15px; color: #555; font-weight: bold; line-height: 1.6;">Good news! Your order has been ACCEPTED and is being PROCESSED.</p>
        <p style="padding-left: 20px; padding-right:20px; font-size: 13px; color: #555; margin-top: 2px;">We are working to get your order ready for shipment. Stay tuned for updates.</p>
        """
    elif status == "Preparing":
        message_content = f"""
        <p style="padding-left: 20px; padding-right:20px; font-size: 15px; color: #555; font-weight: bold; line-height: 1.6;">Your order is now being PREPARED!</p>
        <p style="padding-left: 20px; padding-right:20px; font-size: 13px; color: #555; margin-top: 2px;">We are preparing your orders and getting them ready for packing.</p>
        """
    elif status == "Packed":
        message_content = f"""
        <p style="padding-left: 20px; padding-right:20px; font-size: 15px; color: #555; font-weight: bold; line-height: 1.6;">Your order has been PACKED!</p>
        """
    elif status == "Ready for Pickup":
        message_content = f"""
        <p style="padding-left: 20px; padding-right:20px; font-size: 15px; color: #555; font-weight: bold; line-height: 1.6;">Your order is now READY FOR PICK UP!</p>
        <p style="padding-left: 20px; padding-right:20px; font-size: 15px; color: #555; margin-top: 10px;">Please show this email including your order code.</p>
        """
    elif status == "Out for Delivery":
        message_content = f"""
        <p style="font-size: 15px; color: #008000; font-weight: bold; line-height: 1.6;">Your order is now OUT FOR DELIVERY!</p>
        <p style="padding-left: 20px; padding-right:20px; font-size: 14px; color: #333; margin-top: 10px;">Your order is on its way and should reach you soon! If you have any questions, feel free to reach out.</p>
        """
    elif status == "Completed":
        message_content = f"""
        <p style="font-size: 15px; color: #008000; font-weight: bold; line-height: 1.6;">Your order has been successfully COMPLETED!</p>
        <p style="font-size: 13px; color: #333; margin-top: 10px;">Thank you for shopping with us. We hope you love your purchase! Please feel free to reach out for any future needs.</p>
        """
    elif status == "Void":
        message_content = f"""
        <p style="font-size: 15px; color: #8B0000; font-weight: bold; line-height: 1.6;">
            Your order has been voided.
        </p>
        <p style="font-size: 13px; color: #555; margin-top: 10px;">
            Reason: <span style="color: #333;">{void_reason if void_reason else "No reason specified"}</span>
        </p>
        <p style="font-size: 13px; color: #555; margin-top: 10px;">
            If you have questions, please contact us for assistance.
        </p>
        """
    else:
        message_content = f"""
        <p style="font-size: 15px; color: #333; line-height: 1.6;">Your order status is now {status}.</p>
        <p style="font-size: 13px; color: #333; margin-top: 10px;">We will notify you once there are any changes or updates regarding your order.</p>
        """

    # Build the body of the email
    body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 0; color: #333;">
            <div style="width: 100%; height: 100%; padding: 40px 0;">
                <table align="center" width="700" style="border-collapse: collapse; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08); margin: 0 auto;">
                    
                    <!-- Header -->
                    <tr>
                        <td align="center" style="padding: 25px; background: linear-gradient(135deg, {customization.primary_color} 100%, {customization.secondary_color} 100%); border-top-left-radius: 12px; border-top-right-radius: 12px;">
                            
                            <!-- Business Name (smaller font) -->
                            <p style="font-size: 14px; font-weight: 600; color: {customization.button_text_color}; margin: 0 0 1px 0;">
                                {business.business_name}
                            </p>

                            <!-- Main Title -->
                            <h1 style="font-size: 35px; font-weight: 800; color: {customization.button_text_color}; margin: 0;">
                                ORDER UPDATE
                            </h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 25px; text-align: center; font-size: 18px; line-height: 1.6; color: #555;">
                            
                            <!-- Highlighted Order Code -->
                            <div style="
                                display: inline-block;
                                background-color: {customization.primary_color};
                                color: {customization.button_text_color};
                                font-weight: 800;
                                font-size: 25px;
                                padding: 10px 25px;
                                border-radius: 8px;
                                letter-spacing: 1px;
                                box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
                                margin-top: -10px;
                                margin-bottom: 15px;
                            ">
                                {order_code}
                            </div>

                            <!-- Dynamic Message -->
                            <div class="message" style="font-size: 16px; color: #333; margin-bottom: 20px; line-height: 1.6; text-align: center;">
                                {message_content}
                            </div>

                            <!-- Receipt Section -->
                            <div class="receipt" style="
                                text-align: left; 
                                background: #fafafa; 
                                padding: 15px; 
                                border-radius: 10px; 
                                border: 1px solid #eee; 
                                box-shadow: 0 2px 8px rgba(0,0,0,0.05); 
                                max-width: 580px; 
                                margin: 0 auto; 
                                font-family: 'Courier New', monospace;
                            ">
                                <h3 style="font-size: 18px; font-weight: 800; text-align: center; margin-bottom: 8px;">🧾 Order Summary</h3>
                                <hr style="border: none; border-top: 1px dashed rgba(0,0,0,0.3); margin: 5px 0;">
                                <table width="100%" font-weight:700;  style="border-collapse: collapse; font-size: 14px;">
                                    <thead>
                                        <tr>
                                            <th align="left" style="padding-bottom: 6px;">Item</th>
                                            <th align="right" style="padding-bottom: 6px;">Price</th>
                                        </tr>
                                    </thead>
                                    <tbody style="font-weight:700;">{item_list}</tbody>
                                </table>
                                <hr style="border: none; border-top: 1px dashed rgba(0,0,0,0.3); margin: 10px 0;">
                                <p style="text-align: right; font-weight: 900; font-size: 15px;">Total: ₱{total_price:.2f}</p>
                            </div>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                    <td style="padding: 20px; background-color: #f5f5f5; text-align: center; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px;">
                            <table role="presentation" align="center" cellspacing="0" cellpadding="0" border="0" width="100%" style="text-align: center;">
                                <tr>
                                    <td style="color: {customization.button_text_color}; font-size: 13px; line-height: 1.8; padding: 0 15px;">
                                        <p style="margin: 5px 0;">
                                            <strong>✉️ Email:</strong>
                                            <a href="mailto:{business.email_address}" style="color: {customization.button_text_color}; text-decoration: none; margin-left: 5px;">
                                                {business.email_address}
                                            </a>
                                        </p>
                                        <p style="margin: 5px 0;">
                                            <strong>📞 Contact:</strong> {business.contact_number}
                                        </p>
                                        <p style="margin: 5px 0;">
                                            <strong>📍 Address:</strong> {business.store_address}
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </div>
        </body>
    </html>
    """


    try:
        email = EmailMultiAlternatives(
            subject=subject,
            from_email=django_settings.EMAIL_HOST_USER,
            to=[recipient_email],
        )
        email.attach_alternative(body, "text/html")
        email.send()
        print(f"✅ Email sent to {recipient_email}")
    except Exception as e:
        print(f"❌ Failed to send email to {recipient_email}: {str(e)}")


@csrf_exempt
def update_order_status_progress(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            order_code = data.get('order_code')
            group_id = data.get('group_id')   # ✅ new unique identifier
            status = data.get('status')
            delivery_method = data.get('delivery_method')
            tracking_url = data.get('tracking_url')
            eta_value = data.get('eta_value')
            eta_unit = data.get('eta_unit')
            rider_name = data.get('rider_name')
            void_reason = data.get('void_reason')  # ✅ capture void reason

            if not order_code or not group_id or not status:
                return JsonResponse({'success': False, 'error': 'Missing data'})

            # ✅ Only update this specific order group
            orders = Checkout.objects.filter(order_code=order_code, group_id=group_id)

            if not orders.exists():
                return JsonResponse({'success': False, 'error': 'No active order found for this code'})

            channel_layer = get_channel_layer()

            for order in orders:
                order.status = status
                order.is_seen_by_customer = False  # 🔄 Mark as unseen
                order.updated_at = now()

                # ✅ Save void reason if status is "void"
                if status.lower() == "void":
                    order.void_reason = void_reason
                else:
                    order.void_reason = None

                # ✅ Save delivery method, tracking URL & ETA if applicable
                if status.lower() == "out for delivery":
                    order.delivery_method = delivery_method
                    order.tracking_url = tracking_url if delivery_method == "third_party" else None
                    order.eta_value = eta_value if eta_value else None
                    order.eta_unit = eta_unit if eta_unit else None
                    order.rider = rider_name if delivery_method == "in_house" else None
                else:
                    order.delivery_method = None
                    order.tracking_url = None
                    order.eta_value = None
                    order.eta_unit = None
                    order.rider = None

                order.save()
                
            # ✅ Email notification (sent once for the group)
            reference_order = orders.first()
            send_email_notification(reference_order.email, status, order_code, orders, void_reason=void_reason)

            # ✅ WebSocket Notification
            sanitized_email = reference_order.email.replace('@', 'at').replace('.', 'dot')
            group_name = f"customer_{sanitized_email}"

            customer_count = Checkout.objects.filter(
                email=reference_order.email,
                status__in=["accepted", "rejected", "Preparing", "Packed",
                            "Ready for Pickup", "Out for Delivery", "Completed", "Void"],
                is_seen_by_customer=False,
                group_id=group_id  # ✅ Only this order group
            ).values("order_code").distinct().count()

            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "send_customer_notification",
                    "message": f"Your order has been voided"
                              + (f" ({void_reason})" if void_reason else ""),
                    "customer_count": customer_count,
                }
            )



            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required_session(allowed_roles=['owner', 'cashier'])
def partial_pending_orders(request):
    customization = get_or_create_customization()
    pending_orders = Checkout.objects.filter(status="pending").order_by('-created_at')

    # Group by order_code AND group_id
    grouped = defaultdict(list)
    for order in pending_orders:
        composite_key = f"{order.order_code}_{order.group_id}" if order.group_id else order.order_code
        grouped[composite_key].append(order)

    # Convert to display format with clean order codes
    grouped_orders = []
    for composite_key, items in grouped.items():
        clean_order_code = composite_key.split('_')[0] if '_' in composite_key else composite_key
        grouped_orders.append({
            'order_code': clean_order_code,
            'first': items[0],
            'items': items,
            'total_price': sum(item.price for item in items)
        })

    # Sort by most recent created_at
    grouped_orders.sort(key=lambda x: x['first'].created_at if x['first'].created_at else datetime.min, reverse=True)

    html = render_to_string("partials/pending_orders_list.html", {
        'grouped_orders': grouped_orders,
        'customization': customization,
        'title': 'Notification'
    })
    return HttpResponse(html)
	
def notify_business_owners():
    channel_layer = get_channel_layer()
    pending_count = Checkout.objects.filter(status="pending").count()

    async_to_sync(channel_layer.group_send)(
        "notifications",
        {
            "type": "send_pending_count",
            "count": pending_count
        }
    )

def notify_pending_order():
    from .models import Checkout
    count = Checkout.objects.filter(status='pending').count()

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "notifications",
        {
            "type": "send_notification",
            "message": "New pending order received",
            "count": count
        }
    )

@csrf_exempt
def reject_order(request, order_code):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            reason = data.get("reason", "")
            group_id = data.get("group_id")  # ✅ capture group_id

            if not group_id:
                return JsonResponse({"success": False, "error": "Missing group_id"})

            day_start, day_end = get_business_day_range()

            orders = Checkout.objects.filter(
                order_code=order_code,
                group_id=group_id,
            )

            if not orders.exists():
                return JsonResponse({"success": False, "error": "No matching orders found."})

            for order in orders:
                order.status = "rejected"
                order.rejection_reason = reason
                order.save()

            # ✅ Email notify only once
            send_order_status_email(
                recipient_email=orders[0].email,
                order_code=order_code,
                status="rejected",
                orders=orders,
                rejection_reason=reason
            )

            return JsonResponse({"success": True})

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request"}, status=400)


#CUSTOMIZE FUNCTION WAG GALAWIN #
@login_required_session(allowed_roles=['owner'])
@csrf_exempt
def customization_settings(request):
    if request.method == 'POST':
        # Get or create customization settings
        customization, created = Customization.objects.get_or_create(id=1)

        # Handling background images (ensure old file stays if no new file is uploaded)
        general_background_image = request.FILES.get('general_background_image', None)
        if general_background_image:
            customization.general_background_image = general_background_image

        login_background_image = request.FILES.get('login_background_image', None)
        if login_background_image:
            customization.login_background_image = login_background_image

        register_background_image = request.FILES.get('register_background_image', None)
        if register_background_image:
            customization.register_background_image = register_background_image

        # Handle homepage images
        # Handle homepage images

        # Image 1
        if request.POST.get('remove_homepage_image_1'):
            if customization.homepage_image_1:
                customization.homepage_image_1.delete(save=False)
                customization.homepage_image_1 = None
        else:
            homepage_image_1 = request.FILES.get('homepage_image_1')
            if homepage_image_1:
                customization.homepage_image_1 = homepage_image_1

        # Image 2
        if request.POST.get('remove_homepage_image_2'):
            if customization.homepage_image_2:
                customization.homepage_image_2.delete(save=False)
                customization.homepage_image_2 = None
        else:
            homepage_image_2 = request.FILES.get('homepage_image_2')
            if homepage_image_2:
                customization.homepage_image_2 = homepage_image_2

        # Image 3
        if request.POST.get('remove_homepage_image_3'):
            if customization.homepage_image_3:
                customization.homepage_image_3.delete(save=False)
                customization.homepage_image_3 = None
        else:
            homepage_image_3 = request.FILES.get('homepage_image_3')
            if homepage_image_3:
                customization.homepage_image_3 = homepage_image_3

        # Image 4
        if request.POST.get('remove_homepage_image_4'):
            if customization.homepage_image_4:
                customization.homepage_image_4.delete(save=False)
                customization.homepage_image_4 = None
        else:
            homepage_image_4 = request.FILES.get('homepage_image_4')
            if homepage_image_4:
                customization.homepage_image_4 = homepage_image_4

        # Image 5
        if request.POST.get('remove_homepage_image_5'):
            if customization.homepage_image_5:
                customization.homepage_image_5.delete(save=False)
                customization.homepage_image_5 = None
        else:
            homepage_image_5 = request.FILES.get('homepage_image_5')
            if homepage_image_5:
                customization.homepage_image_5 = homepage_image_5

        # Register background overlay
        # Register Background Image (Overlay)
        if request.POST.get('remove_register_background_image'):
            if customization.register_background_image:
                customization.register_background_image.delete(save=False)
                customization.register_background_image = None
        else:
            register_background_image = request.FILES.get('register_background_image')
            if register_background_image:
                customization.register_background_image = register_background_image


            

        # Update other fields from the form
        customization.general_background_type = request.POST.get('general_background_type')
        customization.general_solid_color = request.POST.get('general_solid_color')
        customization.general_gradient_color_1 = request.POST.get('general_gradient_color_1')
        customization.general_gradient_color_2 = request.POST.get('general_gradient_color_2')
        customization.general_gradient_color_3 = request.POST.get('general_gradient_color_3', None)
        customization.general_gradient_direction = request.POST.get('general_gradient_direction', None)
        customization.general_radial_shape = request.POST.get('general_radial_shape', None)
        customization.general_radial_position = request.POST.get('general_radial_position', None)

        # Other settings (login, register, etc.)
        customization.login_background_type = request.POST.get('login_background_type')
        customization.login_solid_color = request.POST.get('login_solid_color')
        customization.login_gradient_color_1 = request.POST.get('login_gradient_color_1')
        customization.login_gradient_color_2 = request.POST.get('login_gradient_color_2')
        customization.login_gradient_color_3 = request.POST.get('login_gradient_color_3', None)
        customization.login_gradient_direction = request.POST.get('login_gradient_direction')
        customization.login_radial_shape = request.POST.get('login_radial_shape', None)
        customization.login_radial_position = request.POST.get('login_radial_position', None)

        customization.register_background_type = request.POST.get('register_background_type')
        customization.register_solid_color = request.POST.get('register_solid_color')
        customization.register_gradient_color_1 = request.POST.get('register_gradient_color_1')
        customization.register_gradient_color_2 = request.POST.get('register_gradient_color_2')
        customization.register_gradient_color_3 = request.POST.get('register_gradient_color_3', None)
        customization.register_gradient_direction = request.POST.get('register_gradient_direction')
        customization.register_radial_shape = request.POST.get('register_radial_shape', None)
        customization.register_radial_position = request.POST.get('register_radial_position', None)

        # Navigation settings
        customization.navigation_background_type = request.POST.get('navigation_background_type')
        customization.navigation_solid_color = request.POST.get('navigation_solid_color')
        customization.navigation_gradient_color_1 = request.POST.get('navigation_gradient_color_1')
        customization.navigation_gradient_color_2 = request.POST.get('navigation_gradient_color_2')
        customization.navigation_gradient_color_3 = request.POST.get('navigation_gradient_color_3', None)
        customization.navigation_gradient_direction = request.POST.get('navigation_gradient_direction', None)
        customization.navigation_radial_shape = request.POST.get('navigation_radial_shape', None)
        customization.navigation_radial_position = request.POST.get('navigation_radial_position', None)

        # Navigation colors
        customization.navigation_text_color = request.POST.get('navigation_text_color')
        customization.navigation_hover_color = request.POST.get('navigation_hover_color')
        customization.navigation_border_color = request.POST.get('navigation_border_color')

        # Font settings
        customization.header_font_family = request.POST.get('header_font_family')
        customization.header_font_size = int(request.POST.get('header_font_size'))
        customization.header_font_color = request.POST.get('header_font_color')
        customization.header_font_style = request.POST.get('header_font_style')  # Saving the header style here

        customization.body_font_family = request.POST.get('body_font_family')
        customization.body_font_size = int(request.POST.get('body_font_size'))
        customization.body_font_color = request.POST.get('body_font_color')

        # Button and input styles
        customization.button_text_color = request.POST.get('button_text_color')
        customization.input_rounded_corner = int(request.POST.get('input_rounded_corner'))
        customization.primary_color = request.POST.get('primary_color')
        customization.secondary_color = request.POST.get('secondary_color')
        customization.accent_color = request.POST.get('accent_color')
        customization.button_rounded_corner = int(request.POST.get('button_rounded_corner'))
        customization.input_border_width = int(request.POST.get('input_border_width'))
        customization.input_border_style = request.POST.get('input_border_style')

        customization.show_best_sellers = request.POST.get('show_best_sellers', 'off') == 'on'
        customization.best_sellers_title = request.POST.get('best_sellers_title')
        customization.best_sellers_description = request.POST.get('best_sellers_description')

        # Update the dynamic description
        customization.dynamic_description = request.POST.get('dynamic_description')

        # Save the customization settings
        customization.save()

        return redirect('settings')  # Redirect to settings page after saving

    else:
        # If it's a GET request, fetch the customization settings from the database
        customization = Customization.objects.first()

        context = {
            'general_background_type': customization.general_background_type,
            'general_solid_color': customization.general_solid_color,
            'general_gradient_color_1': customization.general_gradient_color_1,
            'general_gradient_color_2': customization.general_gradient_color_2,
            'general_gradient_color_3': customization.general_gradient_color_3,
            'general_gradient_direction': customization.general_gradient_direction,
            'general_radial_shape': customization.general_radial_shape,
            'general_radial_position': customization.general_radial_position,
            'login_background_type': customization.login_background_type,
            'login_solid_color': customization.login_solid_color,
            'login_gradient_color_1': customization.login_gradient_color_1,
            'login_gradient_color_2': customization.login_gradient_color_2,
            'login_gradient_color_3': customization.login_gradient_color_3,
            'login_gradient_direction': customization.login_gradient_direction,
            'login_radial_shape': customization.login_radial_shape,
            'login_radial_position': customization.login_radial_position,
            'register_background_type': customization.register_background_type,
            'register_solid_color': customization.register_solid_color,
            'register_gradient_color_1': customization.register_gradient_color_1,
            'register_gradient_color_2': customization.register_gradient_color_2,
            'register_gradient_color_3': customization.register_gradient_color_3,
            'register_gradient_direction': customization.register_gradient_direction,
            'register_radial_shape': customization.register_radial_shape,
            'register_radial_position': customization.register_radial_position,
            'header_font_family': customization.header_font_family,
            'header_font_size': customization.header_font_size,
            'header_font_color': customization.header_font_color,
            'header_font_style': customization.header_font_style,
            'body_font_family': customization.body_font_family,
            'body_font_size': customization.body_font_size,
            'body_font_color': customization.body_font_color,
            'button_text_color': customization.button_text_color,
            'input_border_width': customization.input_border_width,
            'input_border_style': customization.input_border_style,
            'input_rounded_corner': customization.input_rounded_corner,
            'primary_color': customization.primary_color,
            'secondary_color': customization.secondary_color,
            'accent_color': customization.accent_color,
            'button_rounded_corner': customization.button_rounded_corner,
            'general_background_image': customization.general_background_image,
            'login_background_image': customization.login_background_image,
            'register_background_image': customization.register_background_image,
            'navigation_background_type': customization.navigation_background_type,
            'navigation_solid_color': customization.navigation_solid_color,
            'navigation_gradient_color_1': customization.navigation_gradient_color_1,
            'navigation_gradient_color_2': customization.navigation_gradient_color_2,
            'navigation_gradient_color_3': customization.navigation_gradient_color_3,
            'navigation_gradient_direction': customization.navigation_gradient_direction,
            'navigation_radial_shape': customization.navigation_radial_shape,
            'navigation_radial_position': customization.navigation_radial_position,
            'navigation_text_color': customization.navigation_text_color,
            'navigation_hover_color': customization.navigation_hover_color,
            'navigation_border_color': customization.navigation_border_color,
            'homepage_image_1': customization.homepage_image_1,
            'homepage_image_2': customization.homepage_image_2,
            'homepage_image_3': customization.homepage_image_3,
            'homepage_image_4': customization.homepage_image_4,
            'homepage_image_5': customization.homepage_image_5,
            'dynamic_description': customization.dynamic_description,
        }

        return render(request, 'MSMEOrderingWebApp/settings.html', context)

def get_or_create_customization():
    # Fetch customization settings or create default if not found
    customization, created = Customization.objects.get_or_create(id=1)

    # If newly created, assign default values
    if created:
        customization.general_background_type = 'solid'
        customization.general_solid_color = '#ffffff'
        customization.general_gradient_color_1 = '#ffffff'
        customization.general_gradient_color_2 = '#000000'
        customization.general_gradient_color_3 = None
        customization.general_gradient_direction = None
        customization.general_radial_shape = None
        customization.general_radial_position = None

        # Login background settings
        customization.login_background_type = 'solid'
        customization.login_solid_color = '#ffffff'
        customization.login_gradient_color_1 = '#ffffff'
        customization.login_gradient_color_2 = '#000000'
        customization.login_gradient_color_3 = None
        customization.login_gradient_direction = 'to right'
        customization.login_radial_shape = None
        customization.login_radial_position = None

        # Register background settings
        customization.register_background_type = 'solid'
        customization.register_solid_color = '#ffffff'
        customization.register_gradient_color_1 = '#ffffff'
        customization.register_gradient_color_2 = '#000000'
        customization.register_gradient_color_3 = None
        customization.register_gradient_direction = 'to right'
        customization.register_radial_shape = None
        customization.register_radial_position = None

        # Navigation background settings
        customization.navigation_background_type = 'solid'
        customization.navigation_solid_color = '#ffffff'
        customization.navigation_gradient_color_1 = '#ffffff'
        customization.navigation_gradient_color_2 = '#000000'
        customization.navigation_gradient_color_3 = None
        customization.navigation_gradient_direction = 'to right'
        customization.navigation_radial_shape = None
        customization.navigation_radial_position = None

        # Navigation text, hover, and border color settings
        customization.navigation_text_color = '#000000'
        customization.navigation_hover_color = '#a8a8a8'
        customization.navigation_border_color = '#cccccc'

        # Font settings
        customization.header_font_family = 'Arial'
        customization.header_font_size = 24
        customization.header_font_color = '#000000'
        customization.header_font_style = 'normal'

        # Body font settings
        customization.body_font_family = 'Arial'
        customization.body_font_size = 16
        customization.body_font_color = '#000000'

        # New Fields - Default Values Added
        customization.input_rounded_corner = 1  # Default rounded corner for input fields
        customization.primary_color = "#000000"  # Default primary color
        customization.secondary_color = "#424242"  # Default secondary color
        customization.accent_color = "#303030"  # Default accent color
        customization.button_rounded_corner = 1  # Default rounded corner for buttons
        customization.button_text_color = '#ffffff'
        customization.input_border_width = 1
        customization.input_border_style = 'solid'

        # Homepage image defaults (optional: you may point to a default image path or leave blank)
        customization.homepage_image_1 = None
        customization.homepage_image_2 = None
        customization.homepage_image_3 = None
        customization.homepage_image_4 = None
        customization.homepage_image_5 = None
        
        # Save the default customization settings
        customization.save()

    return customization


@csrf_exempt  # CSRF exemption (ensure it's safe in your application)
@login_required_session(allowed_roles=['owner'])
def reset_customization(request):
    if request.method == 'POST':
        try:
            customization = Customization.objects.get(id=1)

            # General Background
            customization.general_background_type = 'solid'
            customization.general_solid_color = '#ffffff'
            customization.general_gradient_color_1 = '#ffffff'
            customization.general_gradient_color_2 = '#000000'
            customization.general_gradient_color_3 = None
            customization.general_gradient_direction = 'to right'
            customization.general_radial_shape = None
            customization.general_radial_position = None

            # Login Background
            customization.login_background_type = 'solid'
            customization.login_solid_color = '#ffffff'
            customization.login_gradient_color_1 = '#ffffff'
            customization.login_gradient_color_2 = '#000000'
            customization.login_gradient_color_3 = None
            customization.login_gradient_direction = 'to right'
            customization.login_radial_shape = None
            customization.login_radial_position = None

            # Register Background
            customization.register_background_type = 'solid'
            customization.register_solid_color = '#ffffff'
            customization.register_gradient_color_1 = '#ffffff'
            customization.register_gradient_color_2 = '#000000'
            customization.register_gradient_color_3 = None
            customization.register_gradient_direction = 'to right'
            customization.register_radial_shape = None
            customization.register_radial_position = None

            # Navigation Background
            customization.navigation_background_type = 'solid'
            customization.navigation_solid_color = '#ffffff'
            customization.navigation_gradient_color_1 = '#ffffff'
            customization.navigation_gradient_color_2 = '#000000'
            customization.navigation_gradient_color_3 = None
            customization.navigation_gradient_direction = 'to right'
            customization.navigation_radial_shape = None
            customization.navigation_radial_position = None
            customization.navigation_text_color = '#000000'
            customization.navigation_hover_color = '#4b4b4b'
            customization.navigation_border_color = '#cccccc'

            # Fonts
            customization.header_font_family = 'Arial'
            customization.header_font_size = 24
            customization.header_font_color = '#000000'
            customization.header_font_style = 'normal'

            customization.body_font_family = 'Arial'
            customization.body_font_size = 14
            customization.body_font_color = '#000000'

            # Buttons & Inputs
            customization.button_text_color = '#ffffff'
            customization.input_rounded_corner = 1
            customization.primary_color = '#000000'
            customization.secondary_color = '#1F1F1F'
            customization.accent_color = '#6D6D6D'
            customization.button_rounded_corner = 1
            customization.input_border_width = 1
            customization.input_border_style = 'solid'

            # Remove uploaded images
            customization.general_background_image.delete(save=False)
            customization.login_background_image.delete(save=False)
            customization.register_background_image.delete(save=False)
            customization.homepage_image_1.delete(save=False)
            customization.homepage_image_2.delete(save=False)
            customization.homepage_image_3.delete(save=False)
            customization.homepage_image_4.delete(save=False)
            customization.homepage_image_5.delete(save=False)

            # Best Sellers & Dynamic text reset
            customization.show_best_sellers = True
            customization.best_sellers_title = 'Best Sellers'
            customization.best_sellers_description = "Our most popular products loved by customers."
            customization.dynamic_description = "Shop with us today and find what you love!"

            customization.save()

            return JsonResponse({'status': 'success', 'message': 'Customization has been reset to defaults.'})

        except Customization.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Customization settings not found.'}, status=404)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=400)

#CUSTOMIZE FUNCTION WAG GALAWIN #

@login_required_session(allowed_roles=['owner'])
def business_settings(request):
    customization = get_or_create_customization()

    if request.method == 'POST':
        # Get or create the business instance
        business, created = BusinessDetails.objects.get_or_create(id=1)

        # Update fields
        business.business_name = request.POST.get('business_name')
        business.contact_number = request.POST.get('contact_number')
        business.email_address = request.POST.get('email_address')  # Saving the new email
        business.store_address = request.POST.get('store_address')

        # ✅ New fields
        business.business_description = request.POST.get('business_description')
        business.business_mission = request.POST.get('business_mission')
        business.business_vision = request.POST.get('business_vision')

        business.start_day = request.POST.get('start_day')
        business.end_day = request.POST.get('end_day')

        # Convert opening/closing time string to time object
        opening_time_str = request.POST.get('opening_time')
        closing_time_str = request.POST.get('closing_time')

        try:
            business.opening_time = time.fromisoformat(opening_time_str) if opening_time_str else None
        except ValueError:
            business.opening_time = None

        try:
            business.closing_time = time.fromisoformat(closing_time_str) if closing_time_str else None
        except ValueError:
            business.closing_time = None

        # Handle file upload
        if 'logo' in request.FILES:
            business.logo = request.FILES['logo']

        # Handle checkboxes (multi-select)
        business.services_offered = request.POST.getlist('mode_service')
        business.payment_methods = request.POST.getlist('payment_method')

        # ✅ Save specific onsite services (as "_, _, _")
        specific_services = request.POST.getlist('specific_services[]')
        business.specific_onsite_service = ", ".join(specific_services) if specific_services else ""

        try:
            business.base_fare = float(request.POST.get('base_fare', 0))
        except (ValueError, TypeError):
            business.base_fare = 0

        try:
            business.additional_fare_per_km = float(request.POST.get('additional_fare_per_km', 0))
        except (ValueError, TypeError):
            business.additional_fare_per_km = 0

        business.save()

        # ✅ Handle social media
        platforms = request.POST.getlist('social_platform[]')
        usernames = request.POST.getlist('social_username[]')

        # Clear old ones
        SocialMedia.objects.filter(business=business).delete()

        # Save new ones
        for platform, username in zip(platforms, usernames):
            if platform.strip() and username.strip():
                SocialMedia.objects.create(
                    business=business,
                    platform=platform.strip(),
                    username_or_link=username.strip()
                )

        # ✅ Update first_login2 right after saving business
        owner_id = request.session.get('owner_id')
        if owner_id:
            try:
                owner = BusinessOwnerAccount.objects.get(id=owner_id)
                if owner.first_login2:  # only update if still True
                    owner.first_login2 = False
                    owner.save(update_fields=['first_login2'])
            except BusinessOwnerAccount.DoesNotExist:
                pass

        # ✅ Now safely return response
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Settings saved successfully.'})
        else:
            return redirect('dashboard')

    else:
        # Get the owner and business details
        business = BusinessDetails.objects.first()
        owner = BusinessOwnerAccount.objects.first()  # Fetch the Business Owner Account
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        specific_services_list = []
        if business and business.specific_onsite_service:
            specific_services_list = [s.strip() for s in business.specific_onsite_service.split(",") if s.strip()]

        # ✅ Fetch existing social media
        social_media_list = []
        if business:
            social_media_list = business.social_media.all()

        return render(request, 'MSMEOrderingWebApp/settings.html', {
            'business': business,
            'owner': owner,  # Pass the owner object so the email can be accessed
            'days': days,
            'customization': customization,
            'title': 'Settings',
            'specific_services_list': specific_services_list,  # ✅ Pass to template
            'social_media_list': social_media_list,  # ✅ Pass to template
        })

@login_required_session(allowed_roles=['owner'])
@csrf_exempt
def upload_logo(request):
    if request.method == "POST" and 'logo' in request.FILES:
        try:
            business, created = BusinessDetails.objects.get_or_create(id=1)
            business.logo = request.FILES['logo']
            business.save(update_fields=['logo'])  # only update logo
            return JsonResponse({
                'success': True,
                'logo_url': business.logo.url
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required_session(allowed_roles=['owner'])
def change_owner_password(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        owner_id = request.session.get('owner_id')
        if not owner_id:
            messages.error(request, 'You must be logged in to change your password.')
            return redirect('settings')

        try:
            owner = BusinessOwnerAccount.objects.get(id=owner_id)
        except BusinessOwnerAccount.DoesNotExist:
            messages.error(request, 'Business owner not found.')
            return redirect('settings')

        # Check current password
        if owner.password != current_password:
            messages.error(request, 'Current password is incorrect.')
            return redirect('settings')

        # Check password match
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return redirect('settings')

        # Password strength check (optional but recommended)
        import re
        password_regex = r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$'
        if not re.match(password_regex, new_password):
            messages.error(request, 'Password must be at least 8 characters long, and include letters, numbers, and a special character.')
            return redirect('settings')

        # Save new password (as plain text, per your instruction)
        owner.password = new_password
        owner.save()

        messages.success(request, 'Password updated successfully!')
        return redirect('settings')

    return redirect('settings')

def force_change(request):
    owner_id = request.session.get('owner_id')
    if not owner_id:
        messages.error(request, "Session expired. Please login again.")
        return redirect('login')
    
    owner = get_object_or_404(BusinessOwnerAccount, id=owner_id)
    
    if request.method == 'POST':
        new_email = request.POST.get('new_email')
        new_password = request.POST.get('new_password')
        
        # Validate inputs
        if not new_email or not new_password:
            messages.error(request, "Both email and password are required.")
            return redirect('force_change')
        
        # Email validation
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, new_email):
            messages.error(request, "Please enter a valid email address.")
            return redirect('force_change')
        
        # Password validation
        if len(new_password) < 8 or not re.search(r'[A-Za-z]', new_password) \
           or not re.search(r'[0-9]', new_password) \
           or not re.search(r'[^A-Za-z0-9]', new_password):
            messages.error(request, "Password must be at least 8 characters long and include letters, numbers, and special characters.")
            return redirect('force_change')
        
        # Check if email already exists
        if BusinessOwnerAccount.objects.filter(email=new_email).exclude(id=owner.id).exists():
            messages.error(request, "This email is already registered.")
            return redirect('force_change')
        
        try:
            # Update credentials
            owner.email = new_email
            owner.password = new_password  # plain text (insecure!)
            owner.first_login = False
            owner.status = 'not verified'
            
            # Generate verification token
            verification_token = token_urlsafe(32)
            owner.verification_token = verification_token
            owner.save()
            
            # Build verification URL
            verify_url = request.build_absolute_uri(
                f"/verify-email/?{urlencode({'token': verification_token})}"
            )
            
            # Email content
            subject = "Verify Your Updated Email Address"
            text_content = f"Please verify your email by visiting: {verify_url}"
            html_content = f"""
			<html>
                <head>
                    <!-- Montserrat font -->
                    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                </head>
                <body style="font-family: 'Montserrat', Arial, sans-serif; 
                            background: linear-gradient(135deg, #000000 0%, #555555 100%);
                            margin: 0; padding: 40px 10px; color: #fff;">
                
                    <!-- Container with subtle blur and transparency -->
                    <div style="max-width: 580px; margin: 0 auto; 
                                background: rgba(255, 255, 255, 0.25);  /* lighter opacity */
                                border-radius: 30px; padding: 40px 30px; 
                                border: 1px solid rgba(255,255,255,0.15);  /* softer border */
                                box-shadow: 0 6px 24px rgba(0,0,0,0.25);  /* lighter shadow */
                                backdrop-filter: blur(75px); -webkit-backdrop-filter: blur(100px); 
                                position: relative;">
                
                        <!-- Heading -->
                        <h1 style="font-size: 28px; color: #fff; margin: 0 0 15px; font-weight: 800; text-align: center;">
                            VERIFY YOUR UPDATED EMAIL ADDRESS
                        </h1>
                
                        <!-- Paragraph -->
                        <p style="font-size: 16px; color: #fff; line-height: 1.6; margin: 0 0 30px; text-align: center;">
                            You recently updated your email address. Please confirm it below to activate your account and continue using our services.
                        </p>
                
                        <!-- Button -->
                        <div style="text-align: center; margin: 25px 0;">
                            <a href="{verify_url}" style="display: inline-block; padding: 16px 45px; background: #fff; color: #000; 
                                                        text-decoration: none; border-radius: 50px; font-size: 16px; font-weight: 900; 
                                                        letter-spacing: 1.2px; border: 1px solid #fff; transition: all 0.3s ease;">
                                VERIFY UPDATED EMAIL
                            </a>
                        </div>
                
                        <!-- Info Box -->
                        <div style="background: rgba(17,17,17,0.2); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; 
                                    padding: 18px 20px; margin-top: 25px;">
                            <p style="font-size: 14px; color: #fff; margin: 0; text-align: center;">
                                <strong>Didn't request this?</strong><br>If you did not request this change, please ignore this email.
                            </p>
                        </div>
                
                        <!-- Divider -->
                        <div style="margin: 30px auto 20px; width: 50px; height: 2px; background: #fff; border-radius: 2px;"></div>
                
                        <!-- Footer -->
                        <p style="font-size: 13px; color: #fff; text-align: center; margin: 0;">
                            © 2025 Online Ordering System
                        </p>
                    </div>
                </body>
			</html>
			"""

            # Send email
            email_message = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=django_settings.EMAIL_HOST_USER,
                to=[new_email]
            )
            email_message.attach_alternative(html_content, "text/html")
            email_message.send()
            
            messages.success(request, "Email updated successfully! Please check your email and click the verification link to activate your account.")
            return redirect('login')
            
        except Exception as e:
            # Log the error for debugging
            print(f"Error in force_change: {str(e)}")
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('force_change')
    
    return render(request, 'MSMEOrderingWebApp/forcechange.html', {
        'owner': owner
    })

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

         # Get customization and business details, as they are needed throughout
        customization = get_or_create_customization()
        business = BusinessDetails.objects.first()

        # 1. Try BusinessOwnerAccount login
        try:
            owner = BusinessOwnerAccount.objects.get(email=email, password=password)

            request.session['owner_id'] = owner.id
            request.session['user_type'] = 'owner'
            

            if owner.first_login:
                return redirect('force_change')

            if owner.status != 'verified':
                messages.error(request, "Please verify your account first.")
                # Pass the POST data when redirecting to retain input values
                return render(request, 'MSMEOrderingWebApp/login.html', {
                    'email': email, 
                    'password': password,
                    'customization': customization,
                    'business': business
                })

            if owner.first_login2:
                return redirect('settings')
            else:
                return redirect('dashboard')
        except BusinessOwnerAccount.DoesNotExist:
            pass

        try:
            user = User.objects.get(email=email, password=password)

            if user.status != 'verified':
                messages.error(request, "Please verify your account first.")
                return render(request, 'MSMEOrderingWebApp/login.html', {
                    'email': email,
                    'password': password,
                    'customization': customization,
                    'business': business
                })

            if user.access != 'enabled':
                messages.error(request, "Your account access is disabled.")
                return render(request, 'MSMEOrderingWebApp/login.html', {
                    'email': email,
                    'password': password,
                    'customization': customization,
                    'business': business,
                })

            request.session['user_id'] = user.id
            request.session['user_type'] = 'customer'
            request.session['email'] = user.email

            return redirect('customer_home')

        except User.DoesNotExist:
            pass


        # 3. Try StaffAccount login (for Delivery Rider only)
        try:
            staff = StaffAccount.objects.get(email=email, password=password, role='rider')

            if staff.status != 'verified':
                messages.error(request, "Please verify your account first.")
                return render(request, 'MSMEOrderingWebApp/login.html', {
                    'email': email,
                    'password': password,
                    'customization': customization,
                    'business': business
                })

            if staff.access != 'enabled':
                messages.error(request, "Your account access is disabled.")
                return render(request, 'MSMEOrderingWebApp/login.html', {
                    'email': email,
                    'password': password,
                    'customization': customization,
                    'business': business
                })

            request.session['staff_id'] = staff.id
            request.session['user_type'] = 'rider'
            request.session['email'] = staff.email

            return redirect('deliveryrider_home')
        except StaffAccount.DoesNotExist:
            pass

        # StaffAccount login for Cashier
        try:
            staff = StaffAccount.objects.get(email=email, password=password, role='cashier')

            if staff.status != 'verified':
                messages.error(request, "Please verify your account first.")
                return render(request, 'MSMEOrderingWebApp/login.html', {
                    'email': email,
                    'password': password,
                    'customization': customization,
                    'business': business
                })

            if staff.access != 'enabled':
                messages.error(request, "Your account access is disabled.")
                return render(request, 'MSMEOrderingWebApp/login.html', {
                    'email': email,
                    'password': password,
                    'customization': customization,
                    'business': business
                })

            request.session['staff_id'] = staff.id
            request.session['user_type'] = 'cashier'
            request.session['email'] = staff.email

            return redirect('cashier_dashboard')
        except StaffAccount.DoesNotExist:
            pass

        # If none matched
        messages.error(request, "Invalid credentials.")
        return render(request, 'MSMEOrderingWebApp/login.html', {
            'email': email,
            'password': password,
            'customization': customization,
            'business': business
        })

    # GET request: Render login page
    customization = get_or_create_customization()
    business = BusinessDetails.objects.first()

    if request.FILES.get('login_background_image'):
        customization.login_background_image = request.FILES.get('login_background_image')
        customization.save()

    return render(request, 'MSMEOrderingWebApp/login.html', {
        'customization': customization,
        'business': business
    })
	
def logout_view(request):
    request.session.flush()  # Clears all session data
    return redirect('login')

def verify_email(request):
    token = request.GET.get('token')
    if not token:
        print("No token provided")
        return render(request, 'MSMEOrderingWebApp/verification_failed.html')

    # Try User first
    try:
        user = User.objects.get(verification_token=token)
        print(f"User found: {user}")
        if user.status != 'verified':
            user.status = 'verified'
            user.verification_token = None
            user.save()
        return redirect('login')
    except User.DoesNotExist:
        print("User not found")
        pass

    # Then try BusinessOwnerAccount
    try:
        owner = BusinessOwnerAccount.objects.get(verification_token=token)
        print(f"BusinessOwnerAccount found: {owner}")
        if owner.status != 'verified':
            owner.status = 'verified'
            owner.verification_token = None
            owner.save()
        return redirect('login')
    except BusinessOwnerAccount.DoesNotExist:
        print("BusinessOwnerAccount not found")
        pass

    # Then try StaffAccount
    try:
        staff = StaffAccount.objects.get(verification_token=token)
        print(f"StaffAccount found: {staff}")
        if staff.status != 'verified':
            staff.status = 'verified'
            staff.verification_token = None
            staff.save()
        return redirect('login')
    except StaffAccount.DoesNotExist:
        print("StaffAccount not found")
        return render(request, 'MSMEOrderingWebApp/verification_failed.html')

def register_user(request):
    customization = get_or_create_customization()
    business = BusinessDetails.objects.first()
    logo_url = request.build_absolute_uri(business.logo.url) if business and business.logo else 'https://via.placeholder.com/150'
    print(f"Logo URL: {logo_url}")

    if request.method == 'POST':
        # Collect inputs
        form_data = {
            "first_name": request.POST.get("first_name", ""),
            "last_name": request.POST.get("last_name", ""),
            "contact_number": request.POST.get("contact_number", ""),
            "email": request.POST.get("email", ""),
            "address": request.POST.get("address", ""),
            "city": request.POST.get("city", ""),
            "province": request.POST.get("province", ""),
            "zipcode": request.POST.get("zipcode", ""),
        }
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        # Password validation regex
        length_regex = re.compile(r'^.{8,}$')
        letter_number_regex = re.compile(r'(?=.*[a-zA-Z])(?=.*\d)')
        special_char_regex = re.compile(r'[!@#$%^&*(),.?":{}|<>]')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'MSMEOrderingWebApp/register_user.html', {
                "customization": customization,
                "business": business,
                **form_data
            })

        if not length_regex.match(password) or not letter_number_regex.search(password) or not special_char_regex.search(password):
            messages.error(request, "Password must be at least 8 characters long, include both letters and numbers, and contain at least one special character.")
            return render(request, 'MSMEOrderingWebApp/register_user.html', {
                "customization": customization,
                "business": business,
                **form_data
            })

        if User.objects.filter(email=form_data["email"]).exists() or BusinessOwnerAccount.objects.filter(email=form_data["email"]).exists():
            messages.error(request, "Email already exists in the system.")
            return render(request, 'MSMEOrderingWebApp/register_user.html', {
                "customization": customization,
                "business": business,
                **form_data
            })

        if User.objects.filter(password=password).exists() or BusinessOwnerAccount.objects.filter(password=password).exists():
            messages.error(request, "This password is already in use. Please choose a different one.")
            return render(request, 'MSMEOrderingWebApp/register_user.html', {
                "customization": customization,
                "business": business,
                **form_data
            })

        # Generate token
        verification_token = token_urlsafe(32)

        # Save new user
        user = User(
            first_name=form_data["first_name"],
            last_name=form_data["last_name"],
            contact_number=form_data["contact_number"],
            email=form_data["email"],
            address=form_data["address"],
            city=form_data["city"],
            province=form_data["province"],
            zipcode=form_data["zipcode"],
            password=password,
            verification_token=verification_token,
            access='enabled'
        )
        user.save()

        # Create the email verification URL
        verification_url = request.build_absolute_uri(
            f"/verify-email/?{urlencode({'token': verification_token})}"
        )

        # Safe fallbacks
        primary_color = customization.primary_color or "#0F0F0F"
        secondary_color = customization.secondary_color or "#555555"
        business_name = business.business_name if business else "Business Name"
        business_email = business.email_address if business else "email@example.com"
        business_contact = business.contact_number if business else "000-000-0000"
        business_address = business.store_address if business else "Business Address"

        # Email body (responsive)
        body = f"""
        <html>
            <head>
                <!-- Montserrat font -->
                <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body style="font-family: 'Montserrat', Arial, sans-serif; 
                        background: linear-gradient(135deg, {primary_color} 50%, {secondary_color} 100%);
                        margin: 0; padding: 30px 0; color: #fff;">
            
                <!-- Container with subtle blur and transparency -->
                <div class="email-container" style="max-width: 500px; width: 75%; margin: 0 auto; 
                            background: rgba(17, 17, 17, 0.20);                
                            border-radius: 30px; padding: 40px 30px; 
                            border: 2px solid rgba(255,255,255,0.20);  
                            box-shadow: 0 6px 24px rgba(0,0,0,0.35);  
                            backdrop-filter: blur(75px); -webkit-backdrop-filter: blur(55px); 
                            position: relative;">
            
                    <!-- Heading -->
                    <h2 style="text-align: center; font-size: 28px; font-weight: 800; margin-bottom: 15px; color: #FFFFFF;">
                        CUSTOMER EMAIL VERIFICATION
                    </h2>
            
                    <!-- Greeting -->
                    <p style="text-align: center; font-size: 16px; line-height: 1.6; color: #ffffff;">
                        To complete your registration, please click the button below to verify your email address and activate your account.
                    </p>
            
                    <!-- Button as table (email-friendly) -->
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="margin: 20px auto;">
                        <tr>
                            <td align="center" bgcolor="{secondary_color}" style="border-radius: 50px;">
                                <a href="{verification_url}" target="_blank" class="email-button"
                                style="display: inline-block; padding: 15px 35px; font-family: 'Montserrat', Arial, sans-serif; 
                                        font-size: 16px; font-weight: 800; color: #ffffff; text-decoration: none; 
                                        border-radius: 20px;">
                                    VERIFY MY EMAIL
                                </a>
                            </td>
                        </tr>
                    </table>
            
                    <!-- Info Box -->
                    <div style="background: rgba(220, 53, 69, 0.1); border: 1px solid rgba(220, 53, 69, 0.3); border-radius: 6px; padding: 15px; margin-bottom: 30px; text-align: center;">
                        <p style="color: #ffffff; font-size: 13px; font-weight: 700;">
                            ⚠️ <strong>Didn't create this account?</strong> You can safely ignore this email.
                        </p>
                    </div>
            
                    <!-- Divider -->
                    <div style="margin: 30px auto 20px; width: 50px; height: 2px; background: #fff; border-radius: 2px;"></div>
            
                    <!-- Business Name -->
                    <p style="margin-top: 5px; text-align: center; text-transform: uppercase; font-weight: 700; font-size: 15px; color: rgba(255,255,255,0.6); display: block;">
                        - {business_name}
                    </p>
            
                    <!-- Footer -->
                    <div style="margin-top: 10px; text-align: center; font-size: 12px; color: rgba(255,255,255,0.95);">
                        <p style="margin: 5px 0; display: block;">
                            <strong>✉️ Email:</strong> 
                            <a href="mailto:{business_email}" style="color: #FFFFFF; text-decoration: none; margin-left: 5px;">
                                {business_email}
                            </a>
                        </p>
                        <p style="margin: 5px 0; display: block;">
                            <strong>📞 Contact:</strong> {business_contact}
                        </p>
                        <p style="margin: 5px 0; display: block;">
                            <strong>📍 Address:</strong> {business_address}
                        </p>
                    </div>
                </div>
            </body>
        </html>
        """

        # Send email using Django
        try:
            email = EmailMultiAlternatives(
                "Email Verification",
                "Please verify your email using this link: " + verification_url,
                django_settings.EMAIL_HOST_USER,
                [form_data["email"]]
            )
            email.attach_alternative(body, "text/html")
            email.send()
        except Exception as e:
            print(f"Error sending email: {e}")
            return render(request, 'MSMEOrderingWebApp/register_user.html', {
                "error": "Failed to send verification email.",
                "customization": customization,
                "business": business
            })

        # Redirect to login after successful registration
        messages.success(request, "Registration successful! Please check your email to verify your account, then proceed to log in.")
        return redirect('register_user')

    return render(request, 'MSMEOrderingWebApp/register_user.html', {
        'customization': customization,
        'business': business,
    })

@login_required_session(allowed_roles=['owner'])
def dashboard(request):
    customization = get_or_create_customization()
    business = BusinessDetails.objects.first()

    # Count unique orders based on order_code + date combinations
    def count_unique_orders(queryset, use_updated=False):
        unique_orders = set()
        for order in queryset:
            order_date = order.updated_at.date() if use_updated and order.updated_at else (
                order.created_at.date() if order.created_at else None
            )
            composite_key = f"{order.order_code}_{order.group_id}_{order_date}" if order_date else f"{order.order_code}_{order.group_id}"
            unique_orders.add(composite_key)
        return len(unique_orders)

    total_inventory = Products.objects.values('name').distinct().count()
    total_pending = count_unique_orders(Checkout.objects.filter(status__iexact="pending"))

    total_preparing = count_unique_orders(
        Checkout.objects.filter(
            status__in=["accepted", "Preparing", "Packed", "Out for Delivery", "Ready for Pickup", "delivered"]
        )
    )

    total_declined = count_unique_orders(
        Checkout.objects.filter(status__in=["rejected", "Void"])
    )


    # ✅ Completed orders updated today (for stats and sales)
    today = localdate()
    tz = get_current_timezone()
    start_of_day = make_aware(datetime.combine(today, datetime.min.time()), tz)
    end_of_day = make_aware(datetime.combine(today, datetime.max.time()), tz)

    completed_today_qs = Checkout.objects.filter(
        status__iexact="completed",
        updated_at__range=(start_of_day, end_of_day)
    )

    total_completed = count_unique_orders(completed_today_qs, use_updated=True)

    # Group ACCEPTED orders
    ongoing_statuses = ["accepted", "Preparing", "Packed", "Out for Delivery", "Ready for Pickup", "delivered"]
    accepted_orders_raw = Checkout.objects.filter(status__in=ongoing_statuses).order_by('created_at')
    grouped_accepted_orders = defaultdict(list)
    for order in accepted_orders_raw:
        order_date = order.created_at.date() if order.created_at else None
        composite_key = f"{order.order_code}_{order.group_id}"
        grouped_accepted_orders[composite_key].append(order)

    accepted_orders_grouped = []
    for composite_key, items in grouped_accepted_orders.items():
        clean_order_code = composite_key.split('_')[0]
        accepted_orders_grouped.append({
            'order_code': clean_order_code,
            'items': items,
            'first': items[0],
            'total_price': sum(item.price for item in items),
        })
    accepted_orders_grouped.sort(key=lambda x: x['first'].created_at or make_aware(datetime.min, tz))

    # Group UNSUCCESSFUL orders (Rejected + Void)
    unsuccessful_orders_raw = Checkout.objects.filter(
        status__in=["rejected", "Void"]
    ).order_by('-created_at')

    grouped_unsuccessful_orders = defaultdict(list)
    for order in unsuccessful_orders_raw:
        order_date = order.created_at.date() if order.created_at else None
        composite_key = f"{order.order_code}_{order.group_id}"
        grouped_unsuccessful_orders[composite_key].append(order)

    unsuccessful_orders_grouped = []
    for composite_key, items in grouped_unsuccessful_orders.items():
        clean_order_code = composite_key.split('_')[0]
        unsuccessful_orders_grouped.append({
            'order_code': clean_order_code,
            'items': items,
            'first': items[0],
            'total_price': sum(item.price for item in items),
        })
    unsuccessful_orders_grouped.sort(
        key=lambda x: x['first'].created_at or make_aware(datetime.min, tz),
        reverse=True
    )

    # ✅ Completed orders for table (all time)
    completed_all_qs = Checkout.objects.filter(status__iexact="completed").order_by('-updated_at')

    grouped_completed_orders = defaultdict(list)
    for order in completed_all_qs:
        order_date = order.updated_at.date() if order.updated_at else None
        composite_key = f"{order.order_code}_{order.group_id}"
        grouped_completed_orders[composite_key].append(order)

    completed_orders_grouped = []
    total_sales = Decimal("0.00")  # ✅ Daily sales only
    for composite_key, items in grouped_completed_orders.items():
        clean_order_code = composite_key.split('_')[0]
        subtotal = sum(item.price for item in items)

        # ✅ Count sales only if order is completed today
        if items[0].updated_at and start_of_day <= items[0].updated_at <= end_of_day:
            total_sales += subtotal

        completed_orders_grouped.append({
            'order_code': clean_order_code,
            'items': items,
            'first': items[0],
            'total_price': subtotal,
        })
    completed_orders_grouped.sort(
        key=lambda x: x['first'].updated_at or make_aware(datetime.min, tz),
        reverse=True
    )

    riders = StaffAccount.objects.filter(role="rider", access="enabled")

    context = {
        'customization': customization,
        'user': request.user,
        'title': 'Dashboard',
        'business': business,
        'total_inventory': total_inventory,
        'accepted_orders_grouped': accepted_orders_grouped,
        'unsuccessful_orders_grouped': unsuccessful_orders_grouped,
        'completed_orders_grouped': completed_orders_grouped,  # ✅ all completed orders
        'total_pending': total_pending,
        'total_preparing': total_preparing,
        'total_declined': total_declined,
        'total_completed': total_completed,  # ✅ daily completed count
        "riders": riders,
        "total_sales": total_sales,  # ✅ daily sales
    }

    return render(request, 'MSMEOrderingWebApp/dashboard.html', context)

def sales_report_pdf(request):
    report_type = request.GET.get("report_type")
    date_filter = request.GET.get("date_filter")

    orders = Checkout.objects.all()
    period_label = ""

    # --- Apply Date Filtering ---
    if date_filter == "daily":
        daily_date = request.GET.get("daily_date")
        if daily_date:
            start = make_aware(datetime.strptime(daily_date, "%Y-%m-%d"))
            end = start + timedelta(days=1)
            orders = orders.filter(created_at__range=(start, end))
            period_label = f"Daily Report for {start.strftime('%B %d, %Y')}"

    elif date_filter == "weekly":
        weekly_date = request.GET.get("weekly_date")
        if weekly_date:
            year, week = weekly_date.split("-W")
            start = datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w")
            end = start + timedelta(weeks=1)
            start, end = make_aware(start), make_aware(end)
            orders = orders.filter(created_at__range=(start, end))
            period_label = f"Weekly Report ({start.strftime('%b %d, %Y')} - {end.strftime('%b %d, %Y')})"

    elif date_filter == "monthly":
        monthly_date = request.GET.get("monthly_date")
        if monthly_date:
            start = make_aware(datetime.strptime(monthly_date, "%Y-%m"))
            end = make_aware(datetime(start.year + (start.month // 12), (start.month % 12) + 1, 1))
            orders = orders.filter(created_at__range=(start, end))
            period_label = f"Monthly Report for {start.strftime('%B %Y')}"

    elif date_filter == "custom":
        custom_start = request.GET.get("custom_start")
        custom_end = request.GET.get("custom_end")
        if custom_start and custom_end:
            start = make_aware(datetime.strptime(custom_start, "%Y-%m-%d"))
            end = make_aware(datetime.strptime(custom_end, "%Y-%m-%d")) + timedelta(days=1)
            orders = orders.filter(created_at__range=(start, end))
            period_label = f"Custom Report ({start.strftime('%b %d, %Y')} - {(end - timedelta(days=1)).strftime('%b %d, %Y')})"

    # --- Handle no data ---

    if not orders.exists() and request.GET.get("report_type") not in ["inventory", "top_products"]:
        return _generate_no_data_pdf()

    # --- PDF buffer and styles ---
    buffer = io.BytesIO()
    styles = _get_report_styles()

    business = BusinessDetails.objects.first()
    logo_path = business.logo.path if business and business.logo else None
    header_table = _build_report_header(
        logo_path=logo_path,
        business_name=business.business_name if business else "Business Name",
        address=business.store_address if business else "Address",
        email=business.email_address if business else "Email",
        contact=business.contact_number if business else "Contact",
        styles=styles
    )

    # --- Use BaseDocTemplate ---
    doc = BaseDocTemplate(buffer, pagesize=letter,
                          topMargin=0, bottomMargin=50, leftMargin=0, rightMargin=0)

    # --- Frame for body content ---
    body_frame = Frame(
        50,  # left margin
        50,  # bottom margin
        doc.width - 100,  # width
        doc.height - header_table.wrap(doc.width, 0)[1] - 20,  # height minus header
        id='body'
    )

    # --- Draw header on every page ---
    def draw_header(canvas, doc):
        w, h = header_table.wrap(doc.width + doc.leftMargin + doc.rightMargin, 0)
        header_table.drawOn(canvas, 0, doc.pagesize[1] - h)  # top of page

    # --- Page template ---
    template = PageTemplate(id='with_header', frames=[body_frame], onPage=draw_header)
    doc.addPageTemplates([template])

    # --- Build story ---
    story = []
    report_type = request.GET.get("report_type")
    if report_type == "sales":
        story += _generate_sales_report(orders, period_label, styles)
    elif report_type == "orders":
        story += _generate_orders_report(orders, period_label, styles)
    elif report_type == "inventory":
        story += _generate_inventory_report(period_label, styles)
    elif report_type == "top_products":
        story += _generate_products_report(period_label, styles)

    # --- Build PDF ---
    doc.build(story)
    buffer.seek(0)

    filename = f"{report_type}_report_{datetime.now().strftime('%Y%m%d')}.pdf"
    return HttpResponse(buffer, content_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename}"'
    })

from reportlab.platypus import Image, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch

from reportlab.platypus import Image, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors

def _build_report_header(logo_path, business_name, address, email, contact, styles):
    """Generate a modern header with correct spacing, background, and logo separator line."""

    # Only create logo if path exists and is valid
    logo = None
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=70, height=70)
        except:
            logo = None  # If there's any error creating the image, skip it

    # Business Name (uppercase, bold) - centered alignment
    business_name_para = Paragraph(
        f'<font size="18" color="#000000"><b>{business_name.upper()}</b></font>',
        styles["normal"]
    )

    # Address - centered alignment
    address_para = Paragraph(
        f'<font size="10" color="#808080">{address}</font>',
        styles["normal"]
    )

    # Contact info - centered alignment
    contact_para = Paragraph(
        f'<font size="10" color="#808080">{contact} | {email}</font>',
        styles["normal"]
    )

    # Main header - adjust based on whether logo exists
    if logo:
        # With logo: logo on left, details on right
        # Stack with explicit spacers
        details = [
            business_name_para,
            Spacer(1, 10),
            address_para,
            Spacer(1, 1),
            contact_para,
        ]

        # Wrap details in a table cell
        details_table = Table([[d] for d in details], colWidths=[400])
        details_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        header_content = [[logo, details_table]]
        header_table = Table(header_content)
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),

            # Padding for logo + details
            ("LEFTPADDING", (0, 0), (0, 0), 150),
            ("RIGHTPADDING", (0, 0), (0, 0), 0),
            ("TOPPADDING", (0, 0), (0, 0), 12),
            ("BOTTOMPADDING", (0, 0), (0, 0), 12),

            ("LEFTPADDING", (1, 0), (1, 0), 100),
            ("RIGHTPADDING", (1, 0), (1, 0), 20),
            ("TOPPADDING", (1, 0), (1, 0), 18),
            ("BOTTOMPADDING", (1, 0), (1, 0), 18),

            # Background color
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#DBDBDB")),

            # Subtle bottom border
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#8A8A8A")),
        ]))
    else:
        # Without logo: fully centered vertical stack
        header_content = [
            [business_name_para],
            [Spacer(1, 8)],
            [address_para],
            [Spacer(1, 4)],
            [contact_para]
        ]
        
        header_table = Table(header_content)
        header_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            
            # Consistent padding all around
            ("LEFTPADDING", (0, 0), (-1, -1), 50),
            ("RIGHTPADDING", (0, 0), (-1, -1), 50),
            ("TOPPADDING", (0, 0), (0, 0), 20),
            ("BOTTOMPADDING", (-1, -1), (-1, -1), 20),
            
            # Remove padding from spacer rows
            ("TOPPADDING", (0, 1), (0, 1), 0),
            ("BOTTOMPADDING", (0, 1), (0, 1), 0),
            ("TOPPADDING", (0, 3), (0, 3), 0),
            ("BOTTOMPADDING", (0, 3), (0, 3), 0),

            # Background color
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#DBDBDB")),

            # Subtle bottom border
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#8A8A8A")),
        ]))

    return header_table
	
def _get_report_styles():
    """Define consistent styles for all reports"""
    styles = getSampleStyleSheet()
    
    custom_styles = {
        'title': ParagraphStyle("Title", parent=styles["Title"], 
                               fontSize=20, textColor=colors.black, 
                               alignment=1, spaceAfter=5, fontName="Helvetica-Bold"),
        
        'subtitle': ParagraphStyle("Subtitle", parent=styles["Normal"], 
                                  fontSize=12, textColor=colors.grey, 
                                  alignment=1, spaceAfter=15),
        
        'heading': ParagraphStyle("Heading", parent=styles["Heading2"], 
                                 fontSize=14, textColor=colors.black, 
                                 spaceAfter=10, spaceBefore=15, fontName="Helvetica-Bold"),
        
        'normal': ParagraphStyle("Normal", parent=styles["Normal"], 
                                fontSize=10, spaceAfter=8, alignment=0),
        
        'summary': ParagraphStyle("Summary", parent=styles["Normal"], 
                                 fontSize=11, spaceAfter=12, leftIndent=20,
                                 textColor=colors.black, fontName="Helvetica"),
        
        # 🔹 Add missing explanation style
        'explanation': ParagraphStyle("Explanation", parent=styles["Normal"], 
                                     fontSize=10, leading=14, spaceAfter=5,
                                     textColor=colors.black, italic=True)
    }
    
    return custom_styles

def _generate_no_data_pdf():
    """Generate PDF for no data scenarios"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph("No data available for the selected period", styles["Title"])]
    doc.build(story)
    buffer.seek(0)
    return HttpResponse(buffer, content_type="application/pdf", headers={
        "Content-Disposition": 'attachment; filename="no_data_report.pdf"'
    })


def _generate_sales_report(orders, period_label, styles):
    """Generate simplified but comprehensive sales report."""
    story = []
    story.append(Paragraph("SALES REPORT", styles['title']))

    if period_label:
        story.append(Paragraph(period_label, styles['subtitle']))

    # ✅ Only completed orders
    completed_orders = orders.filter(status__iexact="completed").order_by("created_at")

    # ===== GROUP ORDERS =====
    grouped_orders = defaultdict(list)
    for order in completed_orders:
        key = (order.order_code, str(order.group_id))  # ✅ use group_id to distinguish same code orders
        grouped_orders[key].append(order)

    # ===== METRICS =====
    total_revenue = sum(float(order.price) for order in completed_orders)
    total_orders = len(grouped_orders)  # ✅ each group_id is a unique order
    total_items = sum(order.quantity for order in completed_orders)
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

    # ===== EXECUTIVE SUMMARY =====
    story.append(Paragraph("EXECUTIVE SUMMARY", styles['heading']))
    exec_data = [
        ["Metric", "Value"],
        ["Total Sales", f"Php {total_revenue:,.2f}"],
        ["Total Orders", str(total_orders)],
        ["Average Order Value", f"Php {avg_order_value:,.2f}"],
        ["Items Sold", str(total_items)],
    ]
    exec_table = Table(exec_data, colWidths=[200, 150])
    exec_table.setStyle(_get_table_style())
    story.append(exec_table)
    story.append(Spacer(1, 20))

    # ===== SALES SUMMARY =====
    story.append(Paragraph("SALES SUMMARY", styles['heading']))
    story.append(Paragraph("This is a table of all completed orders within the selected period.", styles['summary']))
    story.append(Spacer(1, 10))

    sales_data = [["Customer", "Date & Time", "Order Code", "Ordered Items", "Order Value"]]

    for (order_code, group_id), items in sorted(grouped_orders.items(), key=lambda x: x[1][0].created_at):
        first_order = items[0]
        customer_name = f"{first_order.first_name} {first_order.last_name}"
        order_datetime = first_order.created_at.strftime("%Y-%m-%d %H:%M") if first_order.created_at else ""

        # Bullet list for items
        ordered_items = "<br/>".join([f"• {o.product_name} (x{o.quantity})" for o in items])
        total_value = sum(float(o.price) for o in items)

        sales_data.append([
            customer_name,
            order_datetime,
            order_code,
            Paragraph(ordered_items, styles['normal']),
            f"Php {total_value:,.2f}",
        ])

    sales_table = Table(sales_data, colWidths=[120, 100, 80, 200, 80])
    sales_table.setStyle(_get_table_style())
    story.append(sales_table)
    story.append(Spacer(1, 20))

    # ===== REVENUE BREAKDOWN =====
    story.append(Paragraph("REVENUE BREAKDOWN", styles['heading']))

    # --- Sales by Payment Method (Pie Chart + Totals) ---
    payment_summary = defaultdict(float)
    for order in completed_orders:
        payment_summary[order.payment_method] += float(order.price)

    if payment_summary:
        story.append(Paragraph("Sales by Payment Method", styles['normal']))
        pay_chart = generate_payment_methods_pie_chart(payment_summary)
        story.append(Image(pay_chart, width=250, height=250))
        story.append(Spacer(1, 10))

        pay_data = [["Payment Method", "Total Sales"]]
        for method, total in payment_summary.items():
            pay_data.append([method.title(), f"Php {total:,.2f}"])
        pay_table = Table(pay_data, colWidths=[200, 150])
        pay_table.setStyle(_get_table_style())
        story.append(pay_table)
        story.append(Spacer(1, 20))

    if payment_summary:
        sorted_methods = sorted(payment_summary.items(), key=lambda x: x[1], reverse=True)
        top_method, top_value = sorted_methods[0]
        total_payment_sales = sum(payment_summary.values())
        top_pct = (top_value / total_payment_sales * 100) if total_payment_sales > 0 else 0

        analysis_text = f"The leading payment method is <b>{top_method.title()}</b>, accounting for Php {top_value:,.2f} ({top_pct:.1f}%) of total revenue."
        if len(sorted_methods) > 1:
            second_method, second_value = sorted_methods[1]
            second_pct = (second_value / total_payment_sales * 100) if total_payment_sales > 0 else 0
            analysis_text += f" The second most used is <b>{second_method.title()}</b> at Php {second_value:,.2f} ({second_pct:.1f}%)."
        story.append(Paragraph(analysis_text, styles['summary']))
        story.append(Spacer(1, 20))

    # --- Sales by Order Type (Bar Chart + Totals) ---
    order_type_summary = defaultdict(float)
    for order in completed_orders:
        if order.order_type:
            order_type_summary[order.order_type] += float(order.price)

    if order_type_summary:
        story.append(Paragraph("Sales by Order Type", styles['normal']))
        type_chart = generate_order_types_bar_chart(order_type_summary)
        story.append(Image(type_chart, width=350, height=200))
        story.append(Spacer(1, 10))

        type_data = [["Order Type", "Total Sales"]]
        for otype, total in order_type_summary.items():
            type_data.append([otype.title(), f"Php {total:,.2f}"])
        type_table = Table(type_data, colWidths=[200, 150])
        type_table.setStyle(_get_table_style())
        story.append(type_table)
        story.append(Spacer(1, 20))

        sorted_types = sorted(order_type_summary.items(), key=lambda x: x[1], reverse=True)
        top_type, top_value = sorted_types[0]
        total_type_sales = sum(order_type_summary.values())
        top_pct = (top_value / total_type_sales * 100) if total_type_sales > 0 else 0

        analysis_text = f"The majority of sales come from <b>{top_type.title()}</b> orders, generating Php {top_value:,.2f} ({top_pct:.1f}%)."
        if len(sorted_types) > 1:
            second_type, second_value = sorted_types[1]
            second_pct = (second_value / total_type_sales * 100) if total_type_sales > 0 else 0
            analysis_text += f" In comparison, <b>{second_type.title()}</b> orders contributed Php {second_value:,.2f} ({second_pct:.1f}%)."
        story.append(Paragraph(analysis_text, styles['summary']))
        story.append(Spacer(1, 20))

    # ===== PRODUCT PERFORMANCE BREAKDOWN =====
    story.append(Paragraph("PRODUCT PERFORMANCE BREAKDOWN", styles['heading']))
    product_sales = defaultdict(lambda: {"quantity": 0, "revenue": 0, "unit_price": 0})

    for order in completed_orders:
        variation = getattr(order, 'variation_name', None)
        if variation and variation.lower() != "default":
            key = f"{order.product_name} - {variation}"
        else:
            key = order.product_name

        product_sales[key]["quantity"] += order.quantity
        product_sales[key]["revenue"] += float(order.price)
        product_sales[key]["unit_price"] = (
            float(order.price) / order.quantity if order.quantity > 0 else 0
        )

    if product_sales:
        total_sales = sum(p["revenue"] for p in product_sales.values())
        ranked = sorted(product_sales.items(), key=lambda x: x[1]["revenue"], reverse=True)

        prod_data = [["Rank", "Product", "Unit Price", "Units Sold", "% of Sales"]]
        for i, (prod, data) in enumerate(ranked, 1):
            pct = (data["revenue"] / total_sales * 100) if total_sales > 0 else 0
            prod_data.append([
                str(i),
                prod[:40] + "..." if len(prod) > 40 else prod,
                f"Php {data['unit_price']:,.2f}",
                str(data["quantity"]),
                f"{pct:.1f}%",
            ])

        prod_table = Table(prod_data, colWidths=[40, 200, 80, 80, 80])
        prod_table.setStyle(_get_table_style())
        story.append(prod_table)
        story.append(Spacer(1, 20))

        ranked = sorted(product_sales.items(), key=lambda x: x[1]["revenue"], reverse=True)
        best_product, best_data = ranked[0]
        total_sales = sum(p["revenue"] for p in product_sales.values())
        best_pct = (best_data["revenue"] / total_sales * 100) if total_sales > 0 else 0

        analysis_text = (
            f"The top-performing product is <b>{best_product}</b>, selling {best_data['quantity']} units "
            f"and contributing Php {best_data['revenue']:,.2f} ({best_pct:.1f}% of total sales)."
        )
        if len(ranked) > 1:
            second_product, second_data = ranked[1]
            second_pct = (second_data["revenue"] / total_sales * 100) if total_sales > 0 else 0
            analysis_text += (
                f" The next best-seller is <b>{second_product}</b>, with {second_data['quantity']} units sold "
                f"and Php {second_data['revenue']:,.2f} ({second_pct:.1f}%)."
            )
        story.append(Paragraph(analysis_text, styles['summary']))
        story.append(Spacer(1, 20))

    # ===== TOP CUSTOMERS =====
    story.append(Paragraph("TOP CUSTOMERS BY REVENUE", styles['heading']))
    customer_sales = defaultdict(lambda: {"orders": 0, "revenue": 0})
    for (order_code, group_id), items in grouped_orders.items():
        first_order = items[0]
        key = f"{first_order.first_name} {first_order.last_name}"
        customer_sales[key]["orders"] += 1
        customer_sales[key]["revenue"] += sum(float(o.price) for o in items)

    if customer_sales:
        ranked_customers = sorted(customer_sales.items(), key=lambda x: x[1]["revenue"], reverse=True)[:10]
        cust_data = [["Customer", "Times Ordered", "Total Revenue"]]
        for cust, data in ranked_customers:
            cust_data.append([
                cust,
                str(data["orders"]),
                f"Php {data['revenue']:,.2f}",
            ])
        cust_table = Table(cust_data, colWidths=[150, 100, 120])
        cust_table.setStyle(_get_table_style())
        story.append(cust_table)

    story.append(Spacer(1, 20))
    return story



import matplotlib.pyplot as plt
from io import BytesIO
from collections import defaultdict
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Table, TableStyle, Spacer
from django.utils.text import capfirst
import matplotlib
matplotlib.use('Agg')  # Switch to non-GUI backend

import matplotlib.pyplot as plt


# Define the ongoing statuses
ongoing_statuses = ["accepted", "preparing", "packed", "out for delivery", "ready for pickup", "delivered"]
completed_statuses = ["completed", "delivered", "picked up"]

def generate_order_status_bar_chart(completed, rejected, ongoing, voided=0):
    """Generate a bar chart for order status with improved design and 'Voided' added"""
    labels = ['Completed', 'Voided', 'Rejected', 'Ongoing']
    data = [completed, voided, rejected, ongoing]
    
    # Define colors for the bars
    colors = ['#28a745', '#6c757d', '#dc3545', '#fd7e14']  # Added gray for 'Voided'
    
    # Create the bar chart
    fig, ax = plt.subplots(figsize=(8, 6))
    bars = ax.bar(labels, data, color=colors, edgecolor='black', linewidth=1.5)
    
    # Add grid lines for better readability
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Customize labels and axis
    ax.set_ylabel("Number of Orders", fontsize=12, fontweight='bold')
    ax.set_xlabel("Order Status", fontsize=12, fontweight='bold')
    
    # Add annotations (value labels on top of bars)
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height}', 
                    xy=(bar.get_x() + bar.get_width() / 2, height), 
                    xytext=(0, 3),
                    textcoords="offset points", 
                    ha='center', va='bottom', fontsize=10, fontweight='bold', color='black')
    
    plt.tight_layout()
    
    # Save the chart to a BytesIO object and return it as an image
    img_stream = BytesIO()
    plt.savefig(img_stream, format='png', dpi=300)
    img_stream.seek(0)
    plt.close(fig)
    return img_stream

def generate_order_types_bar_chart(order_types):
    """Generate a bar chart for order types (Dine-in, Pickup, Delivery, etc.)"""
    labels = list(order_types.keys())
    data = list(order_types.values())
    
    fig, ax = plt.subplots(figsize=(8, 6))
    bars = ax.bar(labels, data, color=plt.cm.Set2.colors, edgecolor="black", linewidth=1.5)
    
    ax.set_ylabel("Number of Orders", fontsize=12, fontweight="bold")
    ax.set_xlabel("Order Type", fontsize=12, fontweight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.7)
    
    # Add values above bars
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f"{height}", 
                    xy=(bar.get_x() + bar.get_width()/2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=10, fontweight="bold")
    
    plt.tight_layout()
    img_stream = BytesIO()
    plt.savefig(img_stream, format="png", dpi=300)
    img_stream.seek(0)
    plt.close(fig)
    return img_stream

def generate_payment_methods_pie_chart(payment_methods):
    """Generate a pie chart for payment methods with improved visuals"""
    labels = list(payment_methods.keys())
    data = list(payment_methods.values())
    
    # Create the pie chart
    fig, ax = plt.subplots(figsize=(8, 8))  # Adjust size for better visual appeal
    wedges, texts, autotexts = ax.pie(data, labels=labels, autopct='%1.1f%%', 
                                      colors=plt.cm.Paired.colors, startangle=90, 
                                      wedgeprops={'edgecolor': 'black', 'linewidth': 1.5})
    
    # Customize the text on the chart
    for autotext in autotexts:
        autotext.set_fontsize(15)
        autotext.set_weight('bold')
        autotext.set_color('white')
    
    for text in texts:
        text.set_fontsize(20)
        text.set_weight('bold')
        text.set_color('black')
    
    # Make the pie chart more visually appealing
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    plt.tight_layout()  # To make sure everything fits nicely
    
    # Save the chart to a BytesIO object and return it as an image
    img_stream = BytesIO()
    plt.savefig(img_stream, format='png')
    img_stream.seek(0)
    return img_stream

def _generate_orders_report(orders, period_label, styles): 
    story = []
    story.append(Paragraph("ORDERS REPORT", styles['title']))

    if period_label:
        story.append(Paragraph(period_label, styles['subtitle']))

    # --- Group orders by order_code + group_id ---
    grouped_orders = defaultdict(list)
    for order in orders:
        group_key = (order.order_code, str(order.group_id))  # ✅ use group_id for uniqueness
        grouped_orders[group_key].append(order)

    total_orders = len(grouped_orders)
    completed = rejected = ongoing = pending = voided = 0
    payment_methods = defaultdict(int)
    order_types = defaultdict(int)
    order_details = []

    # Define status groups
    completed_statuses = ["completed"]
    ongoing_statuses = ["accepted", "preparing", "packed", "out for delivery", "ready for pickup", "delivered"]

    for (order_code, group_id), order_items in grouped_orders.items():
        order_items = sorted(order_items, key=lambda o: o.created_at or timezone.now())
        first_order = order_items[0]

        # ✅ Status counters
        status_lower = first_order.status.lower()
        if status_lower in completed_statuses:
            completed += 1
        elif status_lower == "rejected":
            rejected += 1
        elif status_lower == "pending":
            pending += 1
        elif status_lower in ongoing_statuses:
            ongoing += 1
        elif status_lower == "void":
            voided += 1

        # Payment + order type
        payment_methods[first_order.payment_method] += 1
        if hasattr(first_order, "order_type") and first_order.order_type:
            order_types[first_order.order_type] += 1

        total_items = len(order_items)
        order_details.append({
            'date': first_order.created_at.strftime('%m/%d/%Y') if first_order.created_at else '',
            'time': first_order.created_at.strftime('%H:%M:%S') if first_order.created_at else '',
            'order_code': order_code,
            'group_id': group_id,  # ✅ optional (helps debugging)
            'customer': f"{first_order.first_name} {first_order.last_name}",
            'status': first_order.status.title(),
            'payment': first_order.payment_method,
            'total_items': total_items
        })

    # ================= ORDER STATUS SUMMARY =================
    story.append(Paragraph("ORDER STATUS SUMMARY", styles['heading']))

    status_data = [
        ["Status", "Orders", "Percentage"],
        ["Completed", str(completed), f"{(completed / total_orders * 100 if total_orders else 0):.1f}%"],
        ["Voided", str(voided), f"{(voided / total_orders * 100 if total_orders else 0):.1f}%"],
        ["Rejected", str(rejected), f"{(rejected / total_orders * 100 if total_orders else 0):.1f}%"],
        ["Ongoing", str(ongoing), f"{(ongoing / total_orders * 100 if total_orders else 0):.1f}%"],
        ["Pending", str(pending), f"{(pending / total_orders * 100 if total_orders else 0):.1f}%"],
        ["Total Orders", str(total_orders), "100%" if total_orders else "0%"],
    ]

    status_table = Table(status_data, colWidths=[120, 80, 100])
    status_table.setStyle(_get_table_style())
    story.append(status_table)
    story.append(Spacer(1, 15))

    order_status_chart = generate_order_status_bar_chart(completed, rejected, ongoing, voided)
    story.append(Image(order_status_chart, width=400, height=200))
    story.append(Spacer(1, 5))

    # Inline explanation for order status
    if total_orders == 0:
        status_expl = (
            "No orders were recorded during this reporting period, which may reflect a pause "
            "in business activity or a lack of customer engagement."
        )
    else:
        completed_pct = (completed / total_orders) * 100
        rejected_pct = (rejected / total_orders) * 100
        ongoing_pct = (ongoing / total_orders) * 100

        if completed >= rejected and completed >= ongoing:
            dominant = (
                f"A strong majority of transactions were successfully completed "
                f"({completed_pct:.1f}%), demonstrating efficiency in processing and fulfillment. "
                f"This indicates that most customers are receiving their orders as expected."
            )
            caution = (
                f"However, {rejected} orders ({rejected_pct:.1f}%) were rejected and "
                f"{ongoing} ({ongoing_pct:.1f}%) remain in progress, suggesting areas where "
                f"customer experience or order handling could still be improved."
            )
        elif rejected >= completed and rejected >= ongoing:
            dominant = (
                f"Rejections accounted for the largest portion of orders "
                f"({rejected_pct:.1f}%), which may point to recurring issues in "
                f"product availability, payment validation, or customer requirements."
            )
            caution = (
                f"Only {completed} orders ({completed_pct:.1f}%) were completed successfully, "
                f"while {ongoing} ({ongoing_pct:.1f}%) are still pending. "
                f"Reducing rejection rates should be prioritized to improve overall performance."
            )
        else:
            dominant = (
                f"A significant share of orders remain ongoing "
                f"({ongoing_pct:.1f}%), which could signal bottlenecks in preparation or delivery."
            )
            caution = (
                f"Meanwhile, {completed} orders ({completed_pct:.1f}%) were completed and "
                f"{rejected} ({rejected_pct:.1f}%) were rejected. "
                f"Addressing delays in processing will be key to ensuring timely fulfillment."
            )

        status_expl = (
            f"Out of {total_orders} total orders, {completed} were completed, "
            f"{rejected} were rejected, and {ongoing} are ongoing. "
            f"{dominant} {caution}"
        )

    story.append(Paragraph(status_expl, styles['explanation']))
    story.append(Spacer(1, 7))

    # ================= PAYMENT METHODS =================
    story.append(Paragraph("PAYMENT METHODS", styles['heading']))
    payment_data = [["Payment Method", "Orders", "Percentage"]]
    for method, count in sorted(payment_methods.items(), key=lambda x: x[1], reverse=True):
        pct = (count / total_orders * 100) if total_orders > 0 else 0
        payment_data.append([method, str(count), f"{pct:.1f}%"])

    payment_methods_chart = generate_payment_methods_pie_chart(payment_methods)
    story.append(Image(payment_methods_chart, width=200, height=200))

    payment_table = Table(payment_data, colWidths=[150, 80, 80])
    payment_table.setStyle(_get_table_style())
    story.append(payment_table)
    story.append(Spacer(1, 5))

    # Inline explanation for payment methods
    if total_orders == 0 or not payment_methods:
        pay_expl = (
            "No payment method data is available for this period, "
            "which may indicate a lack of recorded transactions."
        )
    else:
        sorted_methods = sorted(payment_methods.items(), key=lambda x: x[1], reverse=True)
        top_method, top_count = sorted_methods[0]
        top_pct = (top_count / total_orders) * 100

        pay_expl = (
            f"Out of {total_orders} total orders, the most preferred payment option "
            f"was <b>{top_method}</b>, selected in {top_count} transactions "
            f"({top_pct:.1f}%). "
        )

        if len(sorted_methods) > 1:
            second_method, second_count = sorted_methods[1]
            second_pct = (second_count / total_orders) * 100
            pay_expl += (
                f"The second most common method was <b>{second_method}</b>, used in "
                f"{second_count} orders ({second_pct:.1f}%). "
            )

            if top_pct >= 70:
                pay_expl += (
                    f"This shows a strong reliance on {top_method}, suggesting customers "
                    f"overwhelmingly prefer this option."
                )
            elif top_pct >= 40:
                pay_expl += (
                    f"While {top_method} leads, a notable share of customers also used "
                    f"{second_method}, indicating diverse preferences."
                )
            else:
                pay_expl += (
                    f"No single method dominates, showing that customers are fairly "
                    f"split in their payment choices."
                )
        else:
            pay_expl += (
                f"Since no other methods were recorded, {top_method} was the only option "
                f"customers relied on for this period."
            )

    story.append(Paragraph(pay_expl, styles['explanation']))
    story.append(Spacer(1, 7))

    # ================= ORDER TYPES =================
    if order_types:
        story.append(Paragraph("ORDER TYPES", styles['heading']))
        order_types_chart = generate_order_types_bar_chart(order_types)
        story.append(Image(order_types_chart, width=400, height=200))
        story.append(Spacer(1, 5))

    sorted_types = sorted(order_types.items(), key=lambda x: x[1], reverse=True)
    if sorted_types:
        top_type, top_count = sorted_types[0]
        top_pct = (top_count / total_orders * 100)
        type_expl = (
            f"Out of {total_orders} total orders, the most common type was "
            f"<b>{top_type}</b>, with {top_count} transactions ({top_pct:.1f}%). "
        )
        if len(sorted_types) > 1:
            second_type, second_count = sorted_types[1]
            second_pct = (second_count / total_orders * 100)
            type_expl += (
                f"The second most frequent type was <b>{second_type}</b>, chosen in "
                f"{second_count} orders ({second_pct:.1f}%). "
            )

            if top_pct >= 70:
                type_expl += f"This indicates a strong customer preference for {top_type}."
            elif top_pct >= 40:
                type_expl += f"Although {top_type} leads, {second_type} also captured a large share."
            else:
                type_expl += "Customers used multiple order types fairly evenly."
        else:
            type_expl += f"{top_type} was the only order type recorded this period."

        story.append(Paragraph(type_expl, styles['explanation']))
        story.append(Spacer(1, 7))

    # ================= ORDER DETAILS =================
    story.append(Paragraph("ORDER DETAILS", styles['heading']))

    order_data = [["Date", "Order Code", "Customer", "Total Items", "Status", "Payment"]]
    for order in order_details:
        order_data.append([
            order['date'],
            order['order_code'],
            order['customer'],
            str(order['total_items']),
            order['status'],
            order['payment']
        ])

    order_table = Table(order_data, colWidths=[70, 80, 120, 80, 80, 80])
    order_table.setStyle(_get_table_style())
    story.append(order_table)
    story.append(Spacer(1, 5))

    # --- Inline Explanation ---
    if not order_details:
        order_expl = (
            "No individual order records were found for this reporting period. "
            "This indicates that no transactions were processed."
        )
    else:
        total_orders = len(order_details)
        completed = sum(1 for o in order_details if o['status'].lower() == "completed")
        rejected = sum(1 for o in order_details if o['status'].lower() == "rejected")
        ongoing = total_orders - completed - rejected

        order_expl = (
            f"The table above provides a detailed breakdown of {total_orders} orders, "
            "including the date of transaction, order code, customer name, total items, "
            "status, and payment method. "
        )

        if completed > max(rejected, ongoing):
            pct = (completed / total_orders) * 100
            order_expl += (
                f"A majority of these orders were successfully completed "
                f"({completed} orders, {pct:.1f}%), reflecting strong order fulfillment."
            )
        elif rejected > max(completed, ongoing):
            pct = (rejected / total_orders) * 100
            order_expl += (
                f"A significant portion of orders were rejected "
                f"({rejected} orders, {pct:.1f}%), highlighting possible order issues."
            )
        elif ongoing > max(completed, rejected):
            pct = (ongoing / total_orders) * 100
            order_expl += (
                f"Many orders remain ongoing ({ongoing} orders, {pct:.1f}%), suggesting active processing."
            )

        payments = {}
        for o in order_details:
            payments[o['payment']] = payments.get(o['payment'], 0) + 1
        if payments:
            top_method = max(payments, key=payments.get)
            top_count = payments[top_method]
            pct = (top_count / total_orders) * 100
            order_expl += (
                f" The most used payment method was <b>{top_method}</b>, "
                f"appearing in {top_count} orders ({pct:.1f}%)."
            )

    story.append(Paragraph(order_expl, styles['explanation']))
    story.append(Spacer(1, 20))

    return story
	
def _generate_inventory_report(period_label, styles):
    story = []
    story.append(Paragraph("INVENTORY REPORT", styles['title']))

    if period_label:
        story.append(Paragraph(period_label, styles['subtitle']))

    products = Products.objects.all()
    
    # --- total unique product names ---
    total_products = products.values("name", "category").distinct().count()

    tracked_products = products.filter(track_stocks=True)
    untracked_products = products.filter(track_stocks=False).values("name", "category").distinct().count()

    # Stock status counts (still per variation, since stocks vary)
    out_of_stock = tracked_products.filter(stocks=0).count()
    low_stock = tracked_products.filter(stocks__lte=5, stocks__gt=0).count()
    normal_stock = tracked_products.filter(stocks__gt=5).count()

    # === Inventory Summary ===
    story.append(Paragraph("INVENTORY SUMMARY", styles['heading']))
    summary_text = f"""
    Total Products: {total_products:,}<br/>
    Tracked Products: {tracked_products.values("name", "category").distinct().count():,}<br/>
    Untracked Products: {untracked_products:,}<br/>
    Out of Stock (variations): {out_of_stock:,}<br/>
    Low Stock (≤5, variations): {low_stock:,}<br/>
    Normal Stock (variations): {normal_stock:,}
    """
    story.append(Paragraph(summary_text, styles['summary']))
    story.append(Spacer(1, 15))

    # === ITEMS NEEDING ATTENTION ===
    critical_items = tracked_products.filter(stocks__lte=5).order_by('stocks')
    if critical_items.exists():
        story.append(Paragraph("ITEMS NEEDING ATTENTION", styles['heading']))
        critical_data = [["Product", "Variation", "Unit Price", "Current Stock", "Status"]]
        
        for product in critical_items[:15]:  # Limit to 15 items
            status = "OUT OF STOCK" if product.stocks == 0 else "LOW STOCK"
            critical_data.append([
                product.name[:40] + "..." if len(product.name) > 40 else product.name,
                product.variation_name or "Standard",
                f"Php {product.price:,.2f}",
                str(product.stocks),
                status
            ])
        
        critical_table = Table(critical_data, colWidths=[180, 100, 80, 80, 100])
        critical_table.setStyle(_get_table_style())
        story.append(critical_table)
        story.append(Spacer(1, 20))

    # === Complete Inventory ===
    story.append(Paragraph("COMPLETE INVENTORY", styles['heading']))
    categories = ProductCategory.objects.all().order_by("name")

    for category in categories:
        category_products = products.filter(category=category).order_by("name")

        # count distinct product names per category
        unique_count = category_products.values("name").distinct().count()
        if unique_count == 0:
            continue

        # Category label with item count
        story.append(Paragraph(f"{category.name} ({unique_count} Items)", styles['subtitle']))
        story.append(Spacer(1, 5))

        # Build table for this category
        inventory_data = [["Product", "Variation", "Unit Price", "Added At", "Sold Count", "Stock Level"]]
        for product in category_products:
            stock_info = str(product.stocks) if product.track_stocks else "Not Tracked"

            inventory_data.append([
                product.name[:40] + "..." if len(product.name) > 40 else product.name,
                product.variation_name or "Standard",
                f"Php {product.price:,.2f}",
                product.created_at.strftime("%m/%d/%y"),
                str(product.sold_count),
                stock_info,
            ])

        inventory_table = Table(inventory_data, colWidths=[140, 100, 80, 80, 80, 80])
        inventory_table.setStyle(_get_table_style())
        story.append(inventory_table)
        story.append(Spacer(1, 15))

    # === Category Distribution Pie Chart ===
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.piecharts import Pie

    category_counts = []
    category_labels = []

    for category in categories:
        # distinct product names per category
        unique_products = Products.objects.filter(category=category).values("name").distinct()
        count = unique_products.count()
        if count > 0:
            category_counts.append(count)
            category_labels.append(category.name)

    if category_counts:
        story.append(Paragraph("CATEGORY DISTRIBUTION", styles['heading']))
        drawing = Drawing(400, 200)
        pie = Pie()
        pie.x = 150
        pie.y = 15
        pie.width = 130
        pie.height = 130
        pie.data = category_counts
        total = sum(category_counts)
        pie.labels = [
            f"{capfirst(label)} ({count}, {count/total:.1%})"
            for label, count in zip(category_labels, category_counts)
        ]
        pie.slices.fontName = "Helvetica" 
        pie.slices.strokeWidth = 0.5
        drawing.add(pie)
        story.append(drawing)
        story.append(Spacer(1, 20))


    # === Edit History ===
    from .models import ProductEditHistory
    history = ProductEditHistory.objects.all().order_by("-updated_at")[:50]
    if history.exists():
        story.append(Paragraph("EDIT HISTORY (Recent)", styles['heading']))
        history_data = [["Product", "Field", "Old Value", "New Value", "Updated At"]]
        for record in history:
            history_data.append([
                record.product.name[:35] + "..." if len(record.product.name) > 35 else record.product.name,
                record.field.capitalize(),
                str(record.old_value),
                str(record.new_value),
                record.updated_at.strftime("%m/%d/%y • %I:%M %p"),
            ])
        history_table = Table(history_data, colWidths=[140, 80, 80, 80, 120])
        history_table.setStyle(_get_table_style())
        story.append(history_table)
        story.append(Spacer(1, 20))

    # === Deleted / Archived Products ===
    from .models import ArchivedProducts
    archived = ArchivedProducts.objects.all().order_by("-archived_at")
    if archived.exists():
        story.append(Paragraph("ARCHIVED PRODUCTS", styles['heading']))
        archived_data = [["Product", "Variation", "Category", "Price", "Archived At"]]
        for p in archived[:50]:
            archived_data.append([
                p.name[:30] + "..." if len(p.name) > 30 else p.name,
                p.variation_name or "Standard",
                p.category.name if p.category else "N/A",
                f"Php {p.price:,.2f}",
                p.archived_at.strftime("%m/%d/%y • %I:%M %p"),
            ])
        archived_table = Table(archived_data, colWidths=[120, 80, 100, 60, 120])
        archived_table.setStyle(_get_table_style())
        story.append(archived_table)
        story.append(Spacer(1, 20))

    return story



import matplotlib.pyplot as plt
from reportlab.platypus import Image, Table, TableStyle, Paragraph, Spacer
import io

def _generate_products_report(period_label, styles):
    """Generate enhanced top products report with tables, charts, and explanations"""
    story = []
    story.append(Paragraph("TOP PRODUCTS REPORT", styles['title']))

    if period_label:
        story.append(Paragraph(period_label, styles['subtitle']))

    products = Products.objects.all().order_by("-sold_count")
    total_products = products.count()
    products_with_sales = products.filter(sold_count__gt=0).count()
    total_units_sold = sum(product.sold_count for product in products)

    # ----------------- SUMMARY -----------------
# ----------------- PRODUCT PERFORMANCE SUMMARY -----------------
    story.append(Paragraph("PRODUCT PERFORMANCE SUMMARY", styles['heading']))

    # ---- Table version of summary ----
    summary_data = [
        ["Total Products", f"{total_products:,}"],
        ["Products with Sales", f"{products_with_sales:,}"],
        ["Total Units Sold", f"{total_units_sold:,}"]
    ]

    if products_with_sales > 0:
        summary_data.append(["Average per Product", f"{(total_units_sold/products_with_sales):.1f} units"])
    else:
        summary_data.append(["Average per Product", "No sales data available"])

    summary_table = Table(summary_data, colWidths=[180, 180])
    summary_table.setStyle(_get_table_style())
    story.append(summary_table)
    story.append(Spacer(1, 15))

    # ---- Bar Chart: Total vs Sales ----
    plt.figure(figsize=(5,4))
    bars = ["Total Products", "With Sales", "Units Sold"]
    values = [total_products, products_with_sales, total_units_sold]

    plt.bar(bars, values, color=["#607D8B", "#4CAF50", "#2196F3"])
    plt.title("Products & Sales Overview")
    plt.ylabel("Count")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close()
    buf.seek(0)
    story.append(Image(buf, width=350, height=250))
    story.append(Spacer(1, 20))

    # ---- Explanation ----
    if products_with_sales == 0:
        explanation = "No products recorded sales during this period, suggesting either low demand or lack of promotion."
    elif products_with_sales == total_products:
        explanation = "All products recorded sales, showing strong overall engagement across the catalog."
    elif products_with_sales > total_products / 2:
        explanation = "More than half of the products achieved sales, with healthy market engagement."
    else:
        explanation = "Less than half of the products recorded sales, highlighting opportunities for marketing or product adjustments."

    story.append(Paragraph(explanation, styles['summary']))
    story.append(Spacer(1, 20))


    # ----------------- TOP 10 PRODUCTS (TABLE + CHART) -----------------
    if products_with_sales > 0:
        story.append(Paragraph("TOP 10 PRODUCTS", styles['heading']))

        top_products = products[:10]
        table_data = [["Rank", "Product", "Units Sold"]]
        for i, p in enumerate(top_products, 1):
            table_data.append([str(i), p.name[:35] + "…" if len(p.name) > 35 else p.name, str(p.sold_count)])

        table = Table(table_data, colWidths=[40, 200, 100])
        table.setStyle(_get_table_style())
        story.append(table)
        story.append(Spacer(1, 10))

        # Bar Chart
        labels = [p.name[:15] + "…" if len(p.name) > 15 else p.name for p in top_products]
        counts = [p.sold_count for p in top_products]

        plt.figure(figsize=(6, 4))
        plt.barh(labels, counts)
        plt.xlabel("Units Sold")
        plt.title("Top 10 Products by Units Sold")
        plt.gca().invert_yaxis()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close()
        buf.seek(0)
        story.append(Image(buf, width=400, height=250))
        story.append(Spacer(1, 10))

        # Explanation
        if counts[0] >= counts[1] * 2:
            explanation = f"The top product ({labels[0]}) significantly outperformed others, selling over twice as much as the next product."
        elif counts[0] == counts[-1]:
            explanation = "All top 10 products sold at nearly the same level, indicating a balanced demand."
        else:
            explanation = f"The top products show varied performance, with {labels[0]} leading at {counts[0]} units."
        story.append(Paragraph(explanation, styles['summary']))
        story.append(Spacer(1, 20))

    # ----------------- PERFORMANCE CATEGORIES (TABLE + PIE) -----------------
    story.append(Paragraph("PERFORMANCE CATEGORIES", styles['heading']))
    high_performers = products.filter(sold_count__gte=50).count()
    medium_performers = products.filter(sold_count__range=(10, 49)).count()
    low_performers = products.filter(sold_count__range=(1, 9)).count()
    no_sales = products.filter(sold_count=0).count()

    category_data = [
        ["Category", "Count", "Action Needed"],
        ["High Performers (50+ units)", str(high_performers), "Maintain inventory"],
        ["Medium Performers (10-49)", str(medium_performers), "Promote more"],
        ["Low Performers (1-9)", str(low_performers), "Review pricing/marketing"],
        ["No Sales", str(no_sales), "Consider discontinuing"]
    ]
    category_table = Table(category_data, colWidths=[150, 80, 150])
    category_table.setStyle(_get_table_style())
    story.append(category_table)
    story.append(Spacer(1, 10))


    # Explanation
    if high_performers > (medium_performers + low_performers + no_sales):
        explanation = "High-performing products dominate overall sales, suggesting strong market favorites."
    elif no_sales > (high_performers + medium_performers + low_performers):
        explanation = "A large portion of products recorded no sales, indicating potential issues in demand, visibility, or pricing."
    else:
        explanation = "Sales are spread across categories, showing both strong performers and areas needing improvement."
    story.append(Paragraph(explanation, styles['summary']))
    story.append(Spacer(1, 20))

    return story


def _get_table_style():
    """Professional monochrome style with strong contrast"""
    return TableStyle([
        # Header - high contrast
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.15, 0.15, 0.15)),  # Dark grey
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        
        # Body
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
        
        # Professional spacing
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 15),
        ("RIGHTPADDING", (0, 0), (-1, -1), 15),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        
        # Monochrome alternating rows
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.Color(0.95, 0.95, 0.95)
        ]),
        
        # Strong borders
        ("LINEBELOW", (0, 0), (-1, 0), 2, colors.black),
        ("BOX", (0, 0), (-1, -1), 1, colors.Color(0.6, 0.6, 0.6)),
        ("INNERGRID", (0, 1), (-1, -1), 0.5, colors.Color(0.8, 0.8, 0.8)),
    ])

    



@login_required_session(allowed_roles=['owner'])
def inventory(request):
    business = BusinessDetails.objects.first()
    categories = ProductCategory.objects.all()
    products = Products.objects.all()
    customization = get_or_create_customization()

    def render_with_form_data():
        """Helper to render with previous inputs"""
        return render(request, 'MSMEOrderingWebApp/inventory.html', {
            'categories': categories,
            'products': products,
            'title': 'Products',
            'customization': customization,
            'business': business,
            'form_data': request.POST
        })

    if request.method == 'POST':
        if 'add_category' in request.POST:
            new_category = request.POST.get('new_category')
            if not new_category:
                messages.error(request, "Category name is required.")
                return render_with_form_data()

            ProductCategory.objects.get_or_create(name=new_category)
            messages.success(request, "New category added.")
            return redirect('inventory')

        elif 'add_product' in request.POST:
            image = request.FILES.get('product_image')
            skip_image = request.POST.get('disable_image')  
            name = request.POST.get('product_name')
            description = request.POST.get('product_description')  
            category_id = request.POST.get('product_category')
            default_price = request.POST.get('default_price')
            default_stocks = request.POST.get('product_stocks')
            variation_names = request.POST.getlist('variation_name[]')
            variation_prices = request.POST.getlist('variation_price[]')
            variation_stocks = request.POST.getlist('variation_stocks[]')
            enable_stocks = request.POST.get('enable_stocks') == 'on'

            if not skip_image and not image:
                messages.error(request, "Product image is required unless you skip image upload.")
                return render_with_form_data()

            if not name or not category_id:
                messages.error(request, "Please fill in all required fields: Product Name and Category.")
                return render_with_form_data()
            
            try:
                category = ProductCategory.objects.get(id=category_id)
            except ProductCategory.DoesNotExist:
                messages.error(request, "Selected category does not exist.")
                return render_with_form_data()

            if variation_names and variation_prices and any(variation_names) and any(variation_prices):
                for i in range(len(variation_names)):
                    vname = variation_names[i].strip()
                    vprice = variation_prices[i].strip()
                    vstocks = variation_stocks[i].strip() if enable_stocks and i < len(variation_stocks) else 0

                    if not vname or not vprice:
                        messages.error(request, "Variation name and price are required for all variations.")
                        return render_with_form_data()

                    Products.objects.create(
                        category=category,
                        image=image if not skip_image else None,
                        name=name,
                        description=description,  
                        variation_name=vname,
                        price=vprice,
                        stocks=vstocks,
                        track_stocks=enable_stocks
                    )
            else:
                if not default_price:
                    messages.error(request, "Price is required for single product.")
                    return render_with_form_data()

                if enable_stocks and not default_stocks:
                    messages.error(request, "Stocks are required if stock tracking is enabled.")
                    return render_with_form_data()

                Products.objects.create(
                    category=category,
                    image=image if not skip_image else None,
                    name=name,
                    description=description,  
                    variation_name='Default',
                    price=default_price,
                    stocks=default_stocks if enable_stocks else 0,
                    track_stocks=enable_stocks
                )

            messages.success(request, "Product saved successfully.")
            return redirect('inventory')

    context = {
        'categories': categories,
        'products': products,
        'title': 'Products',
        'customization': customization,
        'business': business
    }
    return render(request, 'MSMEOrderingWebApp/inventory.html', context)


@login_required_session(allowed_roles=['owner'])
def edit_product_price(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        new_price = request.POST.get('new_price')
        new_stocks = request.POST.get('new_stocks')
        new_description = request.POST.get('new_description')
        new_name = request.POST.get('new_name')  # ✅ Added

        try:
            product = Products.objects.get(id=product_id)

            # ✅ Track name changes
            if new_name is not None and str(product.name) != str(new_name):
                ProductEditHistory.objects.create(
                    product=product,
                    field="name",
                    old_value=product.name,
                    new_value=new_name,
                )
                product.name = new_name

            # ✅ Track price changes
            if new_price is not None and str(product.price) != str(new_price):
                ProductEditHistory.objects.create(
                    product=product,
                    field="price",
                    old_value=product.price,
                    new_value=new_price,
                )
                product.price = new_price

            # ✅ Track stocks changes
            if new_stocks is not None and str(product.stocks) != str(new_stocks):
                ProductEditHistory.objects.create(
                    product=product,
                    field="stocks",
                    old_value=product.stocks,
                    new_value=new_stocks,
                )
                product.stocks = new_stocks

            # ✅ Track description changes
            if new_description is not None and str(product.description or "") != str(new_description):
                ProductEditHistory.objects.create(
                    product=product,
                    field="description",
                    old_value=product.description or "",
                    new_value=new_description,
                )
                product.description = new_description

            product.save()
            messages.success(request, "Product updated successfully.")

        except Products.DoesNotExist:
            messages.error(request, "Product not found.")

    return redirect('inventory')

@login_required_session(allowed_roles=['owner'])
def delete_product(request, product_id):
    product = get_object_or_404(Products, id=product_id)

    # Save selected fields to ArchivedProducts
    ArchivedProducts.objects.create(
        original_id=product.id,
        category=product.category,
        name=product.name,
        variation_name=product.variation_name,
        price=product.price,
        stocks=product.stocks,
        sold_count=product.sold_count,
    )

    # Delete from Products
    product.delete()

    messages.success(request, "Product archived and deleted successfully.")
    return redirect('inventory')

@login_required_session(allowed_roles=['owner'])
def toggle_availability(request, product_id):
    product = get_object_or_404(Products, id=product_id)
    if request.method == 'POST':
        product.available = not product.available
        product.save()

        # Show a toast (Django messages)
        state = "available" if product.available else "unavailable"
        messages.success(request, f"Product “{product.name}” is now {state}.")
    return redirect('inventory')

from django.db.models import Sum
from decimal import Decimal


@login_required_session(allowed_roles=['owner'])
def pos(request):
    business = BusinessDetails.objects.first()
    products = Products.objects.select_related('category').filter(available=True)
    categories = ProductCategory.objects.all()

    # Get total cart quantity for walk-in user
    cart_count = Cart.objects.filter(email="walkin@store.com").aggregate(
        total=Sum('quantity')
    )['total'] or 0

    grouped = defaultdict(list)
    for p in products:
        grouped[p.name].append(p)

    unique_products = []
    for name, group in grouped.items():
        min_price = min(p.price for p in group)
        max_price = max(p.price for p in group)
        category = group[0].category
        image = group[0].image
        total_stocks = sum(p.stocks for p in group) 

        show_stocks = all(p.track_stocks for p in group)

        unique_products.append({
            'name': name,
            'price_range': f"₱{min_price:.2f}" if min_price == max_price else f"₱{min_price:.2f} - ₱{max_price:.2f}",
            'category': category.name,
            'image': image,
            'stocks': total_stocks,
            'show_stocks': show_stocks  
        })
    customization = get_or_create_customization()

    return render(request, 'MSMEOrderingWebApp/pos.html', {
        'products': unique_products,
        'categories': categories,
        'all_products': list(products.values('name', 'variation_name', 'price', 'stocks', 'track_stocks')),
        'cart_count': cart_count,  # 👈 add this
	    'customization': customization,
        'title': 'Point-of-Sale',
        'business': business,
        'cart_url': 'pos_cart',
    })

@login_required_session(allowed_roles=['owner', 'cashier'])
@csrf_exempt
def pos_add_to_cart(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            product_name = data.get('product_name')
            quantity = int(data.get('quantity'))
            price = float(data.get('price'))  # This should be UNIT price, not total

            # Extract name and variation - FIX: Handle multiple dashes properly
            parts = product_name.split(" - ")
            name = parts[0]  # First part is the name
            
            # Join all parts except the first one, then split by " (₱" to remove price part
            variation_with_price = " - ".join(parts[1:]) if len(parts) > 1 else ""
            variation = variation_with_price.split(" (₱")[0] if " (₱" in variation_with_price else variation_with_price

            # Get the product that matches the name and variation
            product = Products.objects.filter(name=name, variation_name=variation).first()

            # ✅ Always save the unit price (base price) - NOT the total
            Cart.objects.create(
                first_name="Walk-in",
                last_name="Customer",
                contact_number="N/A",
                address="In-store",
                email="walkin@store.com",
                product_name=product_name,
                quantity=quantity,
                price=product.price if product else (price / quantity),  # Use DB unit price or calculate unit price
                image=product.image if product and product.image else None
            )

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required_session(allowed_roles=['owner', 'cashier'])
@csrf_exempt
def pos_add_to_cart_variation(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            for item in data.get("items", []):
                product_name = f"{item['productName']} - {item['variationName']}"
                quantity = int(item['quantity'])
                total_price = float(item['price'])  # This comes as total from frontend
                unit_price = total_price / quantity  # Calculate unit price

                # Get product
                product = Products.objects.filter(
                    name=item['productName'], 
                    variation_name=item['variationName']
                ).first()

                Cart.objects.create(
                    first_name="Walk-in",
                    last_name="Customer",
                    contact_number="N/A",
                    address="In-store",
                    email="walkin@store.com",
                    product_name=product_name,
                    quantity=quantity,
                    price=product.price if product else unit_price,  # Use DB unit price or calculated unit price
                    image=product.image if product and product.image else None
                )
            return JsonResponse({'success': True, 'cart_count': Cart.objects.count()})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required_session(allowed_roles=['owner'])
def pos_cart_view(request):
    cart_items = Cart.objects.filter(email="walkin@store.com")
    for item in cart_items:
        item.total = item.price * item.quantity

    subtotal = sum(item.total for item in cart_items)

    customization = get_or_create_customization()

    # Get business settings
    business = BusinessDetails.objects.first()

    # ✅ Get specific services (split into list)
    services = []
    if business and business.specific_onsite_service:
        services = [s.strip() for s in business.specific_onsite_service.split(",") if s.strip()]

    return render(request, 'MSMEOrderingWebApp/pos_cart.html', {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'customization': customization,
        'business': business,
        'services': services,   # ✅ Pass services list for dropdown
        'back_url': 'pos',
		'title': 'Point-of-Sale Cart',
		"payment_url": "business_viewonlinepayment",
    })

@login_required_session(allowed_roles=['owner', 'cashier'])
@csrf_exempt
def remove_cart_item(request, item_id):
    if request.method == 'POST':
        try:
            item = Cart.objects.get(id=item_id)
            item.delete()
            return JsonResponse({'success': True})
        except Cart.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Item not found'})
    return JsonResponse({'success': False, 'error': 'Invalid method'})


@login_required_session(allowed_roles=['owner', 'cashier'])
@csrf_exempt  
def clear_cart_items(request):
    if request.method == 'POST':
        try:
            deleted, _ = Cart.objects.filter(email="walkin@store.com").delete()
            if deleted == 0:
                return JsonResponse({'success': False, 'error': 'No items found to delete'})
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required_session(allowed_roles=['owner', 'cashier'])
@csrf_exempt
def update_pos_cart_quantity(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            cart_id = data.get('cart_id')
            quantity = int(data.get('quantity'))

            cart_item = get_object_or_404(Cart, id=cart_id)
            # ✅ FIX: Don't change the unit price, keep it as is
            # The price field should always store unit price
            cart_item.quantity = quantity
            cart_item.save()

            # Return the new total (unit price * quantity) for frontend display
            new_total = cart_item.price * quantity
            return JsonResponse({'success': True, 'new_total': float(new_total)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required_session(allowed_roles=['owner', 'cashier'])
@csrf_exempt
def pos_place_order(request):
    if request.method == 'POST':
        try:
            cart_items = Cart.objects.filter(email="walkin@store.com")
            if not cart_items.exists():
                return JsonResponse({'success': False, 'error': 'Cart is empty'})

            subtotal = sum(item.price * item.quantity for item in cart_items)
            data = json.loads(request.body)

            payment_method = data.get('payment_method')
            additional_notes = data.get('notes', '')
            proof = None
            cash_given = Decimal(str(data.get('cash_amount', 0))) if data.get('cash_amount') else None
            total = subtotal
            change = cash_given - total if cash_given is not None else None

            order_code = generate_order_code('walkin')

            # ✅ Use business day range
            day_start, day_end = get_business_day_range()
            if Checkout.objects.filter(
                order_code=order_code,
                created_at__gte=day_start,
                created_at__lt=day_end
            ).exists():
                return JsonResponse({'success': False, 'error': 'Duplicate order code for current business day'})

            # ✅ Shared group ID for all items in the same POS transaction
            group_id = uuid.uuid4()

            # ✅ Get specific order type
            specific_order_type = data.get('order_type', None)

            checkout_entries = []
            grouped_sales = {}

            for item in cart_items:
                parts = item.product_name.split(" - ", 1)
                if len(parts) < 2:
                    name = parts[0].strip()
                    variation = ""
                else:
                    name = parts[0].strip()
                    variation = parts[1].split(" (₱")[0].strip()

                try:
                    product = Products.objects.get(
                        name__iexact=name,
                        variation_name__iexact=variation
                    )
                    if product.track_stocks:
                        if product.stocks < item.quantity:
                            return JsonResponse({
                                'success': False,
                                'error': f"Not enough stock for {item.product_name}. Available: {product.stocks}"
                            })
                        product.stocks = max(0, product.stocks - item.quantity)
                        product.save(update_fields=["stocks"])
                except Products.DoesNotExist:
                    print(f"❌ Product not found for: {name} - {variation}")
                except Products.MultipleObjectsReturned:
                    product = Products.objects.filter(
                        name__iexact=name,
                        variation_name__iexact=variation
                    ).first()
                    if product and product.track_stocks:
                        product.stocks = max(0, product.stocks - item.quantity)
                        product.save(update_fields=["stocks"])

                grouped_sales[name.lower()] = grouped_sales.get(name.lower(), 0) + item.quantity

                checkout = Checkout.objects.create(
                    first_name=item.first_name,
                    last_name=item.last_name,
                    contact_number=item.contact_number,
                    address=item.address,
                    email=item.email,
                    image=item.image,
                    product_name=item.product_name,
                    quantity=item.quantity,
                    price=item.price * item.quantity,
                    sub_total=subtotal,
                    order_type="walkin",
                    specific_order_type=specific_order_type,
                    order_code=order_code,
                    payment_method=payment_method,
                    proof_of_payment=proof,
                    additional_notes=additional_notes,
                    status="completed",
                    cash_given=cash_given,
                    change=change,
                    group_id=group_id,  # ✅ same group_id for all walkin items
                )
                checkout_entries.append(checkout)

            # ✅ Bulk update sold_count for all grouped product names
            for base_name, qty in grouped_sales.items():
                Products.objects.filter(name__iexact=base_name).update(
                    sold_count=F("sold_count") + qty
                )

            business = BusinessDetails.objects.first()
            business_name = business.business_name if business else "My Store"
            store_address = business.store_address if business else "Store Address"

            order_data = {
                'order_code': order_code,
                'business_name': business_name,
                'store_address': store_address,
                'payment_method': payment_method,
                'order_type': 'walkin',
                'specific_order_type': specific_order_type,
                'cash_given': float(cash_given) if cash_given else None,
                'change': float(change) if change else None,
                'created_at': timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M'),
                'hide_customer_info': True
            }

            items_data = [
                {
                    'product_name': item.product_name,
                    'quantity': item.quantity,
                    'price': float(item.price),
                }
                for item in checkout_entries
            ]

            # ✅ Send print job
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'printers',
                {
                    'type': 'send_print_job',
                    'data': {
                        'type': 'print',
                        'order': order_data,
                        'items': items_data
                    }
                }
            )

            cart_items.delete()
            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})



from collections import defaultdict
from django.utils.timezone import now
from django.utils.safestring import mark_safe

@login_required_session(allowed_roles=['owner', 'rider'])
def delivery(request):
    business = BusinessDetails.objects.first()
    customization = get_or_create_customization()

    today = now().date()

    # Only include delivery orders with in-house delivery
    delivery_orders_raw = Checkout.objects.filter(
        delivery_method='in_house'
    ).order_by('-created_at')

    # Group by both order_code AND date
    grouped_delivery_orders = defaultdict(list)
    for order in delivery_orders_raw:
        order_date = order.created_at.date() if order.created_at else None
        composite_key = f"{order.order_code}_{order_date}" if order_date else order.order_code
        grouped_delivery_orders[composite_key].append(order)

    # Convert to display format with clean order codes + JSON-safe items
    delivery_orders_grouped = []
    for composite_key, items in grouped_delivery_orders.items():
        clean_order_code = composite_key.split('_')[0] if '_' in composite_key else composite_key
        item_total = sum(item.price for item in items)
        delivery_fee = items[0].delivery_fee or 0
        grand_total = item_total + delivery_fee

        delivery_orders_grouped.append({
            'order_code': clean_order_code,
            'items': items,
            'items_json': mark_safe(json.dumps([
                {"name": i.product_name, "qty": i.quantity}
                for i in items
            ])),
            'first': items[0],
            'created_at': items[0].created_at,
            'status': items[0].status,
            'total_price': item_total,
            'delivery_fee': delivery_fee,   # ✅ now available
            'grand_total': grand_total,     # ✅ now available
        })


    # Sort by creation date (newest first)
    delivery_orders_grouped.sort(key=lambda x: x['created_at'] if x['created_at'] else now(), reverse=True)

    # Count unique orders for statistics
    pending_count = len([group for group in delivery_orders_grouped if group['status'].lower() == 'pending'])
    out_for_delivery_count = len([group for group in delivery_orders_grouped if group['status'].lower() == 'out for delivery'])
    delivered_today_count = len([
        group for group in delivery_orders_grouped
        if group['status'].lower() == 'delivered' and group['first'].updated_at.date() == today
    ])

    context = {
        'customization': customization,
        'title': 'Delivery',
        'business': business,
        'delivery_orders': delivery_orders_grouped,
        'pending_count': pending_count,
        'out_for_delivery_count': out_for_delivery_count,
        'delivered_today_count': delivered_today_count,
    }

    return render(request, 'MSMEOrderingWebApp/delivery.html', context)

def cashier_delivery(request):
    business = BusinessDetails.objects.first()
    customization = get_or_create_customization()

    today = now().date()

    # Only include delivery orders with in-house delivery
    delivery_orders_raw = Checkout.objects.filter(
        delivery_method='in_house'
    ).order_by('-created_at')

    # Group by both order_code AND date
    grouped_delivery_orders = defaultdict(list)
    for order in delivery_orders_raw:
        order_date = order.created_at.date() if order.created_at else None
        composite_key = f"{order.order_code}_{order_date}" if order_date else order.order_code
        grouped_delivery_orders[composite_key].append(order)

    # Convert to display format with clean order codes + JSON-safe items
    delivery_orders_grouped = []
    for composite_key, items in grouped_delivery_orders.items():
        clean_order_code = composite_key.split('_')[0] if '_' in composite_key else composite_key
        item_total = sum(item.price for item in items)
        delivery_fee = items[0].delivery_fee or 0
        grand_total = item_total + delivery_fee

        delivery_orders_grouped.append({
            'order_code': clean_order_code,
            'items': items,
            'items_json': mark_safe(json.dumps([
                {"name": i.product_name, "qty": i.quantity}
                for i in items
            ])),
            'first': items[0],
            'created_at': items[0].created_at,
            'status': items[0].status,
            'total_price': item_total,
            'delivery_fee': delivery_fee,   # ✅ now available
            'grand_total': grand_total,     # ✅ now available
        })


    # Sort by creation date (newest first)
    delivery_orders_grouped.sort(key=lambda x: x['created_at'] if x['created_at'] else now(), reverse=True)

    # Count unique orders for statistics
    pending_count = len([group for group in delivery_orders_grouped if group['status'].lower() == 'pending'])
    out_for_delivery_count = len([group for group in delivery_orders_grouped if group['status'].lower() == 'out for delivery'])
    delivered_today_count = len([
        group for group in delivery_orders_grouped
        if group['status'].lower() == 'delivered' and group['first'].updated_at.date() == today
    ])

    context = {
        'customization': customization,
        'title': 'Delivery',
        'business': business,
        'delivery_orders': delivery_orders_grouped,
        'pending_count': pending_count,
        'out_for_delivery_count': out_for_delivery_count,
        'delivered_today_count': delivered_today_count,
    }

    return render(request, 'MSMEOrderingWebApp/cashier_delivery.html', context)

@login_required_session(allowed_roles=['owner'])
def reviews(request):
    business = BusinessDetails.objects.first()
    customization = get_or_create_customization()

    # Fetch reviews from the database, ordered by submission date
    reviews = CustomerReview.objects.all().order_by('-submitted_at')

    # Prepare context data to pass to the template
    context = {
        'customization': customization,
        'title': 'Reviews',
        'reviews': reviews,
        'business': business
    }

    return render(request, 'MSMEOrderingWebApp/reviews.html', context)

@login_required_session(allowed_roles=['owner'])
def users(request):
    business = BusinessDetails.objects.first()
    customization = get_or_create_customization()

    search_query = request.GET.get('search', '').strip()

    # Fetch verified users and all staff accounts
    users = User.objects.filter(status='verified')
    staff_accounts = StaffAccount.objects.all()

    # Filter users based on search query
    if search_query:
        users = [
            user for user in users
            if (search_query.lower() in user.first_name.lower() or
                search_query.lower() in user.last_name.lower() or
                search_query.lower() in user.email.lower())
        ]

        staff_accounts = [
            staff for staff in staff_accounts
            if (search_query.lower() in staff.first_name.lower() or
                search_query.lower() in staff.last_name.lower() or
                search_query.lower() in staff.email.lower())
        ]

    # Combine Users and Staff into a single list with roles
    user_data = []
    for user in users:
        user_data.append({'user': user, 'role': 'user'})

    for staff in staff_accounts:
        user_data.append({'user': staff, 'role': staff.role})

    # Debugging: Print the IDs
    print("User data:")
    for entry in user_data:
        print(f"{entry['role'].capitalize()} ID: {entry['user'].id}")

    # Sort Users and Staff by access and role
    user_data.sort(key=lambda x: (x['user'].access != 'enabled', x['role'] == 'staff'), reverse=True)

    # Prepare context
    context = {
        'customization': customization,
        'user': request.user,
        'title': 'Users',
        'users': user_data,
        'business': business,
    }

    return render(request, 'MSMEOrderingWebApp/users.html', context)

@login_required_session(allowed_roles=['owner'])
@require_POST
def disable_user(request, role, user_id):
    try:
        if role == 'user':
            user = User.objects.get(id=user_id)
            user.access = 'disabled'
            user.save()
            messages.success(request, f'{user.first_name} {user.last_name} (User) has been disabled.')
        elif role in ['cashier', 'rider']:
            staff = StaffAccount.objects.get(id=user_id)
            staff.access = 'disabled'
            staff.save()
            messages.success(request, f'{staff.first_name} {staff.last_name} ({staff.role.capitalize()}) has been disabled.')
        else:
            messages.error(request, 'Invalid role.')
    except (User.DoesNotExist, StaffAccount.DoesNotExist):
        messages.error(request, 'User or Staff not found.')
    return redirect('users')

@login_required_session(allowed_roles=['owner'])
@require_POST
def enable_user(request, role, user_id):
    try:
        if role == 'user':
            user = User.objects.get(id=user_id)
            user.access = 'enabled'
            user.save()
            messages.success(request, f'{user.first_name} {user.last_name} (User) has been enabled.')
        elif role in ['cashier', 'rider']:
            staff = StaffAccount.objects.get(id=user_id)
            staff.access = 'enabled'
            staff.save()
            messages.success(request, f'{staff.first_name} {staff.last_name} ({staff.role.capitalize()}) has been enabled.')
        else:
            messages.error(request, 'Invalid role.')
    except (User.DoesNotExist, StaffAccount.DoesNotExist):
        messages.error(request, 'User or Staff not found.')
    return redirect('users')

@login_required_session(allowed_roles=['owner'])
def create_staff_account(request):
    business = BusinessDetails.objects.first()
    customization = get_or_create_customization()

    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        contact_number = request.POST.get('contact_number')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirmPassword')
        role = request.POST.get('role')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('users')

        if StaffAccount.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect('users')

        # ✅ Generate verification token
        verification_token = token_urlsafe(32)

        # ✅ Create staff account with status 'not verified'
        staff = StaffAccount.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            contact_number=contact_number,
            password=password,  # ⚠️ Consider hashing
            role=role,
            status='not verified',
            verification_token=verification_token
        )

        # ✅ Build verification URL
        verify_url = request.build_absolute_uri(
            f"/verify-email/?{urlencode({'token': verification_token})}"
        )


        # ✅ Prepare email body
        body = f"""
        <html>
            <head>
                <!-- Montserrat font -->
                <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">
            </head>
            <body style="font-family: 'Montserrat', Arial, sans-serif; 
                        background: linear-gradient(135deg, {customization.primary_color or "#0F0F0F"} 50%, {customization.secondary_color or '#555555'} 100%);
                        margin: 0; padding: 40px 0; color: #fff;">

                <!-- Container with subtle blur and transparency -->
                <div class="email-container" style="max-width: 500px; width: 75%; margin: 0 auto; 
                            background: rgba(17, 17, 17, 0.20);                
                            border-radius: 30px; padding: 40px 30px; 
                            border: 2px solid rgba(255,255,255,0.20);  
                            box-shadow: 0 6px 24px rgba(0,0,0,0.35);  
                            backdrop-filter: blur(75px); -webkit-backdrop-filter: blur(55px); 
                            position: relative;">

                    <!-- Heading -->
                    <h2 style="text-align: center; font-size: 28px; font-weight: 700; margin-bottom: 15px; color: #FFFFFF;">
                        STAFF EMAIL VERIFICATION
                    </h2>

                    <!-- Greeting -->
                    <p style="text-align: center; font-size: 16px; line-height: 1.6; color: #ffffff;">
                        Hello {first_name}, please verify your email to activate your account:
                    </p>

                    <!-- Button as table (email-friendly) -->
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="margin: 20px auto;">
                        <tr>
                            <td align="center" bgcolor="{customization.primary_color or '#000000'}" style="border-radius: 50px;">
                                <a href="{verify_url}" target="_blank" 
                                style="display: inline-block; padding: 15px 35px; font-family: 'Montserrat', Arial, sans-serif; 
                                        font-size: 16px; font-weight: 800; color: #ffffff; text-decoration: none; 
                                        border-radius: 20px;">
                                    VERIFY MY EMAIL
                                </a>
                            </td>
                        </tr>
                    </table>

                    <!-- Info text -->
                    <p style="text-align: center; font-size: 14px; color: rgba(255,255,255,0.95);">
                        If you did not request this, please ignore this email.
                    </p>

                    <!-- Divider -->
                    <div style="margin: 30px auto 20px; width: 50px; height: 2px; background: #fff; border-radius: 2px;"></div>

                    <!-- Footer -->
                    <p style=" font-size: 13px; color: #fff; text-align: center; margin: 0;">
                        © 2025 Online Ordering System
                    </p>
                </div>
            </body>
        </html>
        """
       
        try:
            # ✅ Use Django email system
            email_message = EmailMultiAlternatives(
                subject="Verify Your Email Address",
                body="Please verify your email by clicking the link provided.",  # fallback text
                from_email=django_settings.EMAIL_HOST_USER,
                to=[email],
            )
            email_message.attach_alternative(body, "text/html")
            email_message.send()
        except Exception as e:
            messages.error(request, f"Failed to send verification email: {e}")
            return redirect('users')

        messages.success(
            request,
            f"{role.capitalize()} account created successfully. Please verify your email to activate the account."
        )
        return redirect('users')

    return redirect('users')


@login_required_session(allowed_roles=['owner'])
def settings(request):
    # Get or create customization
    customization = get_or_create_customization()

    # Prepare context for rendering the dashboard
    context = {
        'customization': customization,
        'title': 'Settings',
    }
    return render(request, 'MSMEOrderingWebApp/settings.html', context)

@login_required_session(allowed_roles=['owner'])
def business_dashboard(request):
    # Get or create customization
    customization = get_or_create_customization()

    # Get the business details (replace with filter if needed per user)
    business = BusinessDetails.objects.first()

    # Pass both customization and business to the template
    return render(request, 'MSMEOrderingWebApp/business_owner_base.html', {
        'customization': customization,
        'business': business
    })

@login_required_session(allowed_roles=['customer'])
def customer_dashboard(request):
    # Get or create customization settings
    customization = get_or_create_customization()

    # Render with customization context
    return render(request, 'MSMEOrderingWebApp/customer_base.html', {
        'customization': customization,
    })

@login_required_session(allowed_roles=['rider'])
def deliveryrider_dashboard(request):
    customization = get_or_create_customization()

    return render(request, 'MSMEOrderingWebApp/deliveryrider_base.html', {
        'customization': customization,
    })

@login_required_session(allowed_roles=['cashier'])
def cashier_dashboard(request):
    customization = get_or_create_customization()
    business = BusinessDetails.objects.first()

    # Count unique orders based on order_code + date combinations
    def count_unique_orders(queryset, use_updated=False):
        unique_orders = set()
        for order in queryset:
            order_date = order.updated_at.date() if use_updated and order.updated_at else (
                order.created_at.date() if order.created_at else None
            )
            composite_key = f"{order.order_code}_{order.group_id}_{order_date}" if order_date else f"{order.order_code}_{order.group_id}"
            unique_orders.add(composite_key)
        return len(unique_orders)

    total_inventory = Products.objects.values('name').distinct().count()
    total_pending = count_unique_orders(Checkout.objects.filter(status__iexact="pending"))

    total_preparing = count_unique_orders(
        Checkout.objects.filter(
            status__in=["accepted", "Preparing", "Packed", "Out for Delivery", "Ready for Pickup", "delivered"]
        )
    )

    total_declined = count_unique_orders(
        Checkout.objects.filter(status__in=["rejected", "Void"])
    )


    # ✅ Completed orders updated today (for stats and sales)
    today = localdate()
    tz = get_current_timezone()
    start_of_day = make_aware(datetime.combine(today, datetime.min.time()), tz)
    end_of_day = make_aware(datetime.combine(today, datetime.max.time()), tz)

    completed_today_qs = Checkout.objects.filter(
        status__iexact="completed",
        updated_at__range=(start_of_day, end_of_day)
    )

    total_completed = count_unique_orders(completed_today_qs, use_updated=True)

    # Group ACCEPTED orders
    ongoing_statuses = ["accepted", "Preparing", "Packed", "Out for Delivery", "Ready for Pickup", "delivered"]
    accepted_orders_raw = Checkout.objects.filter(status__in=ongoing_statuses).order_by('created_at')
    grouped_accepted_orders = defaultdict(list)
    for order in accepted_orders_raw:
        order_date = order.created_at.date() if order.created_at else None
        composite_key = f"{order.order_code}_{order.group_id}"
        grouped_accepted_orders[composite_key].append(order)

    accepted_orders_grouped = []
    for composite_key, items in grouped_accepted_orders.items():
        clean_order_code = composite_key.split('_')[0]
        accepted_orders_grouped.append({
            'order_code': clean_order_code,
            'items': items,
            'first': items[0],
            'total_price': sum(item.price for item in items),
        })
    accepted_orders_grouped.sort(key=lambda x: x['first'].created_at or make_aware(datetime.min, tz))

    # Group UNSUCCESSFUL orders (Rejected + Void)
    unsuccessful_orders_raw = Checkout.objects.filter(
        status__in=["rejected", "Void"]
    ).order_by('-created_at')

    grouped_unsuccessful_orders = defaultdict(list)
    for order in unsuccessful_orders_raw:
        order_date = order.created_at.date() if order.created_at else None
        composite_key = f"{order.order_code}_{order.group_id}"
        grouped_unsuccessful_orders[composite_key].append(order)

    unsuccessful_orders_grouped = []
    for composite_key, items in grouped_unsuccessful_orders.items():
        clean_order_code = composite_key.split('_')[0]
        unsuccessful_orders_grouped.append({
            'order_code': clean_order_code,
            'items': items,
            'first': items[0],
            'total_price': sum(item.price for item in items),
        })
    unsuccessful_orders_grouped.sort(
        key=lambda x: x['first'].created_at or make_aware(datetime.min, tz),
        reverse=True
    )

    # ✅ Completed orders for table (all time)
    completed_all_qs = Checkout.objects.filter(status__iexact="completed").order_by('-updated_at')

    grouped_completed_orders = defaultdict(list)
    for order in completed_all_qs:
        order_date = order.updated_at.date() if order.updated_at else None
        composite_key = f"{order.order_code}_{order.group_id}"
        grouped_completed_orders[composite_key].append(order)

    completed_orders_grouped = []
    total_sales = Decimal("0.00")  # ✅ Daily sales only
    for composite_key, items in grouped_completed_orders.items():
        clean_order_code = composite_key.split('_')[0]
        subtotal = sum(item.price for item in items)

        # ✅ Count sales only if order is completed today
        if items[0].updated_at and start_of_day <= items[0].updated_at <= end_of_day:
            total_sales += subtotal

        completed_orders_grouped.append({
            'order_code': clean_order_code,
            'items': items,
            'first': items[0],
            'total_price': subtotal,
        })
    completed_orders_grouped.sort(
        key=lambda x: x['first'].updated_at or make_aware(datetime.min, tz),
        reverse=True
    )

    riders = StaffAccount.objects.filter(role="rider", access="enabled")

    context = {
        'customization': customization,
        'user': request.user,
        'title': 'Dashboard',
        'business': business,
        'total_inventory': total_inventory,
        'accepted_orders_grouped': accepted_orders_grouped,
        'unsuccessful_orders_grouped': unsuccessful_orders_grouped,
        'completed_orders_grouped': completed_orders_grouped,  # ✅ all completed orders
        'total_pending': total_pending,
        'total_preparing': total_preparing,
        'total_declined': total_declined,
        'total_completed': total_completed,  # ✅ daily completed count
        "riders": riders,
        "total_sales": total_sales,  # ✅ daily sales
    }

    return render(request, 'MSMEOrderingWebApp/cashier_dashboard.html', context)

@login_required_session(allowed_roles=['cashier'])
def cashier_pos(request):
    business = BusinessDetails.objects.first()
    products = Products.objects.select_related('category').filter(available=True)
    categories = ProductCategory.objects.all()

    # Walk-in cart total
    cart_count = Cart.objects.filter(email="walkin@store.com").aggregate(
        total=Sum('quantity')
    )['total'] or 0

    grouped = defaultdict(list)
    for p in products:
        grouped[p.name].append(p)

    unique_products = []
    for name, group in grouped.items():
        min_price = min(p.price for p in group)
        max_price = max(p.price for p in group)
        category = group[0].category
        image = group[0].image
        total_stocks = sum(p.stocks for p in group)
        show_stocks = all(p.track_stocks for p in group)

        unique_products.append({
            'name': name,
            'price_range': f"₱{min_price:.2f}" if min_price == max_price else f"₱{min_price:.2f} - ₱{max_price:.2f}",
            'category': category.name,
            'image': image,
            'stocks': total_stocks,
            'show_stocks': show_stocks
        })

    customization = get_or_create_customization()

    return render(request, 'MSMEOrderingWebApp/cashier_pos.html', {
        'products': unique_products,
        'categories': categories,
        'all_products': list(products.values('name', 'variation_name', 'price', 'stocks')),
        'cart_count': cart_count,
        'customization': customization,
        'title': 'Point-Of-Sale',
        'business': business,
        'cart_url': 'cashier_poscart',
    })

@login_required_session(allowed_roles=['cashier'])
def cashier_pos_cart_view(request):
    cart_items = Cart.objects.filter(email="walkin@store.com")
    for item in cart_items:
        item.total = item.price * item.quantity

    subtotal = sum(item.total for item in cart_items)

    customization = get_or_create_customization()

    # Get business settings to pass to the cart
    business = BusinessDetails.objects.first()
    
    return render(request, 'MSMEOrderingWebApp/cashier_poscart.html', {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'customization': customization,
        'business': business,  # Pass business settings
        'back_url': 'cashier_pos',
		'title': 'Point-Of-Sale Cart',
		"payment_url": "cashier_viewonlinepayment",
    })

@login_required_session(allowed_roles=['cashier'])
def cashier_notifications(request):

    raw_orders = Checkout.objects.filter(status="pending").order_by('-created_at')
    grouped_orders = defaultdict(list)
    
    for order in raw_orders:
        order_date = order.created_at.date() if order.created_at else None
        composite_key = f"{order.order_code}_{order_date}" if order_date else order.order_code
        grouped_orders[composite_key].append(order)

    # Convert to display format with clean order codes
    final_orders = []
    for composite_key, items in grouped_orders.items():
        clean_order_code = composite_key.split('_')[0] if '_' in composite_key else composite_key
        total_price = sum(float(item.price) for item in items)
        final_orders.append({
            "order_code": clean_order_code,
            "items": items,
            "first": items[0],
            "total_price": total_price
        })

    # Sort by most recent date
    final_orders.sort(key=lambda x: x['first'].created_at if x['first'].created_at else datetime.min, reverse=True)

    business = BusinessDetails.objects.first()
    customization = get_or_create_customization()

    return render(request, 'MSMEOrderingWebApp/cashier_notification.html', {
        'grouped_orders': final_orders,
        'business': business,
        'customization': customization,
        'title': 'Notifications'
    })


@login_required_session(allowed_roles=['rider'])
def deliveryrider_home(request):
    business = BusinessDetails.objects.first()
    customization = get_or_create_customization()

    today = now().date()

    # Only include delivery orders with in-house delivery
    delivery_orders_raw = Checkout.objects.filter(
        delivery_method='in_house'
    ).order_by('-created_at')

    # Group by both order_code AND date
    grouped_delivery_orders = defaultdict(list)
    for order in delivery_orders_raw:
        order_date = order.created_at.date() if order.created_at else None
        composite_key = f"{order.order_code}_{order_date}" if order_date else order.order_code
        grouped_delivery_orders[composite_key].append(order)

    # Convert to display format with clean order codes + JSON-safe items
    delivery_orders_grouped = []
    for composite_key, items in grouped_delivery_orders.items():
        clean_order_code = composite_key.split('_')[0] if '_' in composite_key else composite_key
        delivery_orders_grouped.append({
            'order_code': clean_order_code,
            'group_id': str(items[0].group_id),
            'items': items,
            'items_json': mark_safe(json.dumps([
                {"name": i.product_name, "qty": i.quantity}
                for i in items
            ])),
            'first': items[0],
            'created_at': items[0].created_at,
            'status': items[0].status,
            'total_price': sum(item.price for item in items),
        })

    # Sort by creation date (newest first)
    delivery_orders_grouped.sort(key=lambda x: x['created_at'] if x['created_at'] else now(), reverse=True)

    # Count unique orders for statistics
    pending_count = len([group for group in delivery_orders_grouped if group['status'].lower() == 'pending'])
    out_for_delivery_count = len([group for group in delivery_orders_grouped if group['status'].lower() == 'out for delivery'])
    delivered_today_count = len([
        group for group in delivery_orders_grouped
        if group['status'].lower() == 'delivered' and group['first'].updated_at.date() == today
    ])

    context = {
        'customization': customization,
        'title': 'Delivery',
        'business': business,
        'delivery_orders': delivery_orders_grouped,
        'pending_count': pending_count,
        'out_for_delivery_count': out_for_delivery_count,
        'delivered_today_count': delivered_today_count,
    }

    return render(request, 'MSMEOrderingWebApp/deliveryrider_home.html', context)

@login_required_session(allowed_roles=['rider'])
def mark_as_delivered(request):
    order_code = request.POST.get('order_code')
    group_id = request.POST.get('group_id')  # ✅ require group_id
    proof = request.FILES.get('proof_delivery')

    if not order_code or not group_id or not proof:
        messages.error(request, "Missing order code, group ID, or file.")
        return redirect('deliveryrider_home')  # or your actual page name

    # ✅ Get all items for this exact order group
    orders = Checkout.objects.filter(order_code=order_code, group_id=group_id)

    if not orders.exists():
        messages.error(request, "Order not found or already completed.")
        return redirect('deliveryrider_home')

    for order in orders:
        order.status = 'delivered'
        order.proof_of_delivery = proof
        order.save()

    messages.success(request, f"Order #{order_code} marked as delivered.")
    return redirect('deliveryrider_home')

@login_required_session(allowed_roles=['owner'])
def business_notifications(request):
    # Mark unseen pending orders as seen
    Checkout.objects.filter(status="pending", is_seen_by_owner=False).update(is_seen_by_owner=True)

    # WebSocket badge update - count unique order_code + group_id combinations
    raw_pending = Checkout.objects.filter(status="pending")
    unique_orders = set()
    for order in raw_pending:
        composite_key = f"{order.order_code}_{order.group_id}" if order.group_id else order.order_code
        unique_orders.add(composite_key)
    
    pending_count = len(unique_orders)
    unseen_count = Checkout.objects.filter(status="pending", is_seen_by_owner=False).count()

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "notifications", {
            "type": "send_pending_count",
            "unseen_count": unseen_count,
            "pending_count": pending_count,
        }
    )

    # Group orders by order_code AND group_id
    raw_orders = Checkout.objects.filter(status="pending").order_by('-created_at')
    grouped_orders = defaultdict(list)
    
    for order in raw_orders:
        composite_key = f"{order.order_code}_{order.group_id}" if order.group_id else order.order_code
        grouped_orders[composite_key].append(order)

    # Convert to display format with clean order codes
    final_orders = []
    for composite_key, items in grouped_orders.items():
        clean_order_code = composite_key.split('_')[0] if '_' in composite_key else composite_key
        total_price = sum(float(item.price) for item in items)
        final_orders.append({
            "order_code": clean_order_code,
            "items": items,
            "first": items[0],
            "total_price": total_price
        })

    # Sort by most recent created_at
    final_orders.sort(key=lambda x: x['first'].created_at if x['first'].created_at else datetime.min, reverse=True)

    business = BusinessDetails.objects.first()
    customization = get_or_create_customization()

    return render(request, 'MSMEOrderingWebApp/business_notification.html', {
        'grouped_orders': final_orders,
        'business': business,
        'customization': customization,
        'title': 'Notifications'
    })
	
@login_required_session(allowed_roles=['customer'])
def customer_home(request):
    business = BusinessDetails.objects.first()
    customization = get_or_create_customization()
    products = Products.objects.select_related('category').filter(available=True)
    categories = ProductCategory.objects.all()

    # Group products by name
    grouped = defaultdict(list)
    for p in products:
        grouped[p.name].append(p)

    unique_products = []
    best_seller_products = []
    for name, group in grouped.items():
        min_price = min(p.price for p in group)
        max_price = max(p.price for p in group)
        representative = group[0]

        price_range = (
            f"₱{min_price:.2f}"
            if min_price == max_price
            else f"₱{min_price:.2f} - ₱{max_price:.2f}"
        )

        product_data = {
            'name': name,
            'price_range': price_range,
            'category': representative.category.name if representative.category else "Uncategorized",
            'image': representative.image if representative.image else None,
            'stocks': sum(p.stocks for p in group),
            'track_stocks': representative.track_stocks,
            'sold_count': representative.sold_count,  # ✅ keep sold_count here
        }

        unique_products.append(product_data)

        # ✅ Add to best sellers only if sold_count >= 3
        if representative.sold_count >= 3:
            best_seller_products.append(product_data)

    # ✅ Sort best sellers by sold_count and take top 3
    best_seller_products = sorted(best_seller_products, key=lambda x: x['sold_count'], reverse=True)[:3]

    # Format times to HH:MM:SS (ignore microseconds)
    current_time = datetime.now().strftime("%H:%M:%S")
    opening_time = business.opening_time.strftime("%H:%M:%S")
    closing_time = business.closing_time.strftime("%H:%M:%S")

    return render(request, 'MSMEOrderingWebApp/customer_home.html', {
        'products': unique_products,
        'categories': categories,
        'all_products': list(products.values('name', 'variation_name', 'price', 'stocks', 'track_stocks', 'description')),
        'customization': customization,
        'best_seller_products': best_seller_products,
        'business': business,
        'show_best_sellers': customization.show_best_sellers,
        'best_sellers_title': customization.best_sellers_title,
        'best_sellers_description': customization.best_sellers_description,
        'dynamic_description': customization.dynamic_description,
        'current_time': current_time,
        'opening_time': opening_time,
        'closing_time': closing_time,
    })

@login_required_session(allowed_roles=['cashier', 'rider'])
def staff_profile(request):
    # Ensure the user is logged in as staff
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, "You must be logged in as staff to view this page.")
        return redirect('login')

    # Fetch staff data
    try:
        staff_data = StaffAccount.objects.get(id=staff_id)
    except StaffAccount.DoesNotExist:
        messages.error(request, "Staff account not found.")
        return redirect('login')

    # Decide which base template to extend depending on role
    if staff_data.role == 'cashier':
        base_template = 'MSMEOrderingWebApp/cashier_base.html'
    elif staff_data.role == 'rider':
        base_template = 'MSMEOrderingWebApp/deliveryrider_base.html'
    else:
        base_template = 'MSMEOrderingWebApp/base.html'  # fallback

    # Pass customization & business info
    business = BusinessDetails.objects.first()
    customization = get_or_create_customization()

    context = {
        'customization': customization,
        'business': business,
        'user_data': staff_data,
		'title':'Profile',
        'base_template': base_template
    }

    return render(request, 'MSMEOrderingWebApp/staff_profile.html', context)

@login_required_session(allowed_roles=['owner'])
def update_customization(request):
    customization = get_object_or_404(Customization, pk=1)
    if request.method == 'POST':
        for i in range(1, 6):
            file = request.FILES.get(f'homepage_image_{i}')
            if file:
                setattr(customization, f'homepage_image_{i}', file)

        customization.best_sellers_title = request.POST.get('best_sellers_title', 'Best Sellers')
        customization.show_best_sellers = 'show_best_sellers' in request.POST
        customization.save()
        messages.success(request, "Homepage settings updated.")
        return redirect('settings')

    return render(request, 'settings.html', {'customization': customization})




from .models import CustomerReview, ReviewPhoto, User

@login_required_session(allowed_roles=['customer'])
def customer_reviews(request):
    business = BusinessDetails.objects.first()
    customization = get_or_create_customization()

    if request.method == 'POST':
        user = User.objects.get(id=request.session['user_id'])
        review_text = request.POST.get('review')
        rating = request.POST.get('rating')
        is_anonymous = 'anonymous' in request.POST
        photos = request.FILES.getlist('photos')

        if is_anonymous:
            review = CustomerReview.objects.create(
                name="Anonymous",
                email="",
                contact_number="",
                rating=int(rating),
                review=review_text,
                submitted_at=timezone.now(),
                anonymous=True
            )
        else:
            review = CustomerReview.objects.create(
                user=user,
                rating=int(rating),
                review=review_text,
                submitted_at=timezone.now(),
                anonymous=False
            )

        # Save up to 3 review photos
        for photo in photos[:3]:
            ReviewPhoto.objects.create(review=review, image=photo)

        return redirect('customer_reviews')

    # Fetch reviews
    reviews = (CustomerReview.objects
               .filter(is_hidden=False)
               .select_related('user')
               .order_by('-submitted_at'))

    # Format times to HH:MM:SS
    current_time = datetime.now().strftime("%H:%M:%S")
    opening_time = business.opening_time.strftime("%H:%M:%S") if business and business.opening_time else "00:00:00"
    closing_time = business.closing_time.strftime("%H:%M:%S") if business and business.closing_time else "23:59:59"

    return render(request, 'MSMEOrderingWebApp/customer_reviews.html', {
        'reviews': reviews,
        'customization': customization,
        'business': business,
        'current_time': current_time,
        'opening_time': opening_time,
        'closing_time': closing_time,
    })


@login_required_session(allowed_roles=['customer'])
def customer_cart(request):
    business = BusinessDetails.objects.first()
    if 'user_id' in request.session and request.session.get('user_type') == 'customer':
        user = User.objects.get(id=request.session['user_id'])
        cart_items = Cart.objects.filter(email=user.email)
        
        # Get product data for each cart item - FIXED parsing logic
        for item in cart_items:
            # Fix: Handle multiple dashes properly
            parts = item.product_name.split(' - ')
            if len(parts) >= 2:
                product_name = parts[0]  # First part is always the product name
                # Join all remaining parts as the variation name
                variation_name = ' - '.join(parts[1:])
            else:
                product_name = item.product_name
                variation_name = 'Default'
            
            # Find the matching product
            item.product = Products.objects.filter(
                name=product_name, 
                variation_name=variation_name
            ).first()
        
        subtotal = sum(item.price for item in cart_items)
        customization = get_or_create_customization()
        
        return render(request, 'MSMEOrderingWebApp/customer_cart.html', {
            'cart_items': cart_items,
            'subtotal': subtotal,
            'customization': customization,
            'business': business,
            'user_email': user.email,
        })
    else:
        return redirect('login')

@login_required_session(allowed_roles=['customer'])
def delete_cart_item(request, cart_id):
    if request.method == 'POST':
        cart_item = get_object_or_404(Cart, id=cart_id)
        cart_item.delete()
    return redirect('customer_cart')

@login_required_session(allowed_roles=['customer'])
@csrf_exempt
def update_cart(request, cart_id):
    if request.method == 'POST':
        if 'user_id' not in request.session or request.session.get('user_type') != 'customer':
            return JsonResponse({'success': False, 'error': 'Not authenticated'})

        try:
            data = json.loads(request.body)
            new_qty = int(data.get('quantity', 1))

            cart_item = Cart.objects.get(id=cart_id)
            unit_price = float(cart_item.price) / cart_item.quantity  # price per unit
            updated_price = round(unit_price * new_qty, 2)

            cart_item.quantity = new_qty
            cart_item.price = updated_price
            cart_item.save()

            # Recalculate subtotal
            user = User.objects.get(id=request.session['user_id'])
            cart_items = Cart.objects.filter(email=user.email)
            subtotal = sum(item.price for item in cart_items)

            return JsonResponse({
                'success': True,
                'updated_price': f"{updated_price:.2f}",
                'new_subtotal': f"{subtotal:.2f}"
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})

def generate_order_code(order_type):
    if order_type == 'delivery':
        prefix = 'DL'
    elif order_type == 'pickup':
        prefix = 'PU'
    elif order_type == 'walkin':
        prefix = 'WI'
    else:
        prefix = 'XX'

    # Get business opening time
    business = BusinessDetails.objects.first()  # adjust if multiple businesses
    opening_time = business.opening_time  # stored as time (e.g. 08:00:00)

    now = timezone.localtime()  # current local datetime
    today_opening = datetime.combine(now.date(), opening_time, tzinfo=now.tzinfo)

    # If before opening today, use yesterday’s opening for reset reference
    if now < today_opening:
        reset_reference = today_opening - timezone.timedelta(days=1)
    else:
        reset_reference = today_opening

    # Get latest order for this type since reset_reference
    last_order = Checkout.objects.filter(
        order_type=order_type,
        created_at__gte=reset_reference
    ).order_by('-created_at').first()

    if last_order and last_order.order_code.startswith(prefix):
        try:
            # Extract numeric part
            last_number = int(last_order.order_code.replace(prefix, ''))
        except ValueError:
            last_number = 0
    else:
        last_number = 0

    next_number = last_number + 1
    return f"{prefix}{str(next_number).zfill(3)}"

from django.urls import reverse

@login_required_session(allowed_roles=['customer'])
@csrf_exempt
def customer_checkout(request):
    if 'user_id' not in request.session or request.session.get('user_type') != 'customer':
        return redirect('login')

    user = User.objects.get(id=request.session['user_id'])
    cart_items = Cart.objects.filter(email=user.email)
    subtotal = sum(item.price for item in cart_items)

    delivery_fee = Decimal(request.GET.get('delivery_fee', '0') or '0')
    
    # Fix: Get scheduled_at from GET parameters (from cart form)
    scheduled_date_str = request.GET.get('scheduled_at')  # Changed from 'scheduled_date'
    scheduled_at = None
    if scheduled_date_str:
        try:
            # Parse the datetime string
            scheduled_at = datetime.strptime(scheduled_date_str, "%Y-%m-%dT%H:%M")
            # Make it timezone aware
            scheduled_at = timezone.make_aware(scheduled_at)
        except ValueError as e:
            print(f"Date parsing error: {e}")
            scheduled_at = None

    total_with_fee = subtotal + delivery_fee
    business = BusinessDetails.objects.first()
    customization = get_or_create_customization()

    # Build enriched cart
    cart_data = []
    for item in cart_items:
        product_image = None
        try:
            # ✅ Safe split (supports 2 or 3+ parts)
            parts = item.product_name.split(" - ", 1)
            name = parts[0].strip()
            variation = parts[1].split(" (₱")[0].strip() if len(parts) > 1 else ""

            product = Products.objects.get(
                name__iexact=name,
                variation_name__iexact=variation
            )
            product_image = product.image
        except Exception as e:
            print(f"Image fetch error for {item.product_name}: {e}")

        cart_data.append({
            "product_name": item.product_name,
            "quantity": item.quantity,
            "price": item.price,
            "image": product_image,
        })

    if request.method == 'POST':
        order_type = request.GET.get('order_type') or request.POST.get('order_type')
        payment_method = request.POST.get('payment_method')
        notes = request.POST.get('notes')
        proof = request.FILES.get('proof') if payment_method == 'online' else None
        delivery_fee_post = Decimal(request.POST.get('delivery_fee', '0') or '0')

        # Fix: Get scheduled date from POST data OR use the one from GET
        scheduled_date_post = request.POST.get('scheduled_date')
        if scheduled_date_post:
            try:
                scheduled_at = datetime.strptime(scheduled_date_post, "%Y-%m-%dT%H:%M")
                scheduled_at = timezone.make_aware(scheduled_at)
            except ValueError as e:
                print(f"POST date parsing error: {e}")
                # Keep the scheduled_at from GET if POST parsing fails
                pass

        order_code = generate_order_code(order_type)
        group_id = str(uuid.uuid4())

        # Stock validation
        for item in cart_items:
            try:
                parts = item.product_name.split(" - ", 1)
                name = parts[0].strip()
                variation = parts[1].split(" (₱")[0].strip() if len(parts) > 1 else ""

                product = Products.objects.get(
                    name__iexact=name,
                    variation_name__iexact=variation
                )

                # ✅ Check stock and preserve order_type on redirect
                if product.track_stocks and product.stocks < item.quantity:
                    messages.error(request, f"Not enough stocks for {item.product_name}. Available: {product.stocks}")
                    return redirect(f"{reverse('customer_checkout')}?order_type={request.POST.get('order_type', '')}")
                    
            except Exception as e:
                messages.error(request, str(e))
                return redirect(f"{reverse('customer_checkout')}?order_type={request.POST.get('order_type', '')}")

        # Create Checkout records
        for item in cart_items:
            product_image = None
            try:
                parts = item.product_name.split(" - ", 1)
                name = parts[0].strip()
                variation = parts[1].split(" (₱")[0].strip() if len(parts) > 1 else ""

                product = Products.objects.get(
                    name__iexact=name,
                    variation_name__iexact=variation
                )
                product_image = product.image
            except:
                pass

            checkout = Checkout.objects.create(
                first_name=user.first_name,
                last_name=user.last_name,
                contact_number=user.contact_number,
                address=f"{user.address}, {user.city}, {user.province}, {user.zipcode}",
                email=user.email,
                image=product_image,
                product_name=item.product_name,
                quantity=item.quantity,
                price=item.price,
                sub_total=subtotal,
                order_type=order_type,
                payment_method=payment_method,
                proof_of_payment=proof,
                additional_notes=notes,
                order_code=order_code,
                group_id=group_id,
                delivery_fee=delivery_fee_post,
                scheduled_at=scheduled_at,  # This should now work
            )
            
            # Debug log
            print(f"Created order with scheduled_at: {checkout.scheduled_at}")

        # 🚫 Removed stock deduction here

        cart_items.delete()
        messages.success(request, "Order placed. Check your notifications to see the progress of your order.")
        return redirect('customer_home')

    return render(request, 'MSMEOrderingWebApp/customer_checkout.html', {
        'user': user,
        'cart_items': cart_data,
        'subtotal': subtotal,
        'delivery_fee': delivery_fee,
        'total_with_fee': total_with_fee,
        'customization': customization,
        'business': business,
        'scheduled_date_str': scheduled_date_str,  # Pass for template display
        'scheduled_at': scheduled_at,  # Add this for debugging
    })

@login_required_session(allowed_roles=['customer'])
def customer_notifications(request):
    email = request.session.get('email')
    business = BusinessDetails.objects.first()
    customization, _ = Customization.objects.get_or_create(pk=1)

    # Mark all unseen accepted/rejected notifications as seen
    Checkout.objects.filter(
        email=email,
        status__in=[
            "accepted", "rejected",
            "Preparing", "Packed", "Out for Delivery", "Completed", "delivered"
        ],
        is_seen_by_customer=False
    ).update(is_seen_by_customer=True)

    # Group by both order_code AND date
    all_orders = Checkout.objects.filter(
        email=email,
        status__in=[
            "accepted", "rejected", "Preparing", "Packed", 
            "Ready for Pickup", "Out for Delivery", "Completed", "Void", "delivered"
        ]
    ).order_by('-created_at')

    grouped_orders = defaultdict(list)
    for order in all_orders:
        # Create composite key with order_code + date
        order_date = order.created_at.date() if order.created_at else None
        composite_key = f"{order.order_code}_{order_date}" if order_date else order.order_code
        grouped_orders[composite_key].append(order)

    # Convert to display format
    grouped_notifications = []
    for composite_key, items in grouped_orders.items():
        # Extract clean order code for display
        clean_order_code = composite_key.split('_')[0] if '_' in composite_key else composite_key
        first_item = items[0]
        grouped_notifications.append({
            'order_code': clean_order_code,
            'status': first_item.status,
            'created_at': first_item.created_at,
            'items': items,
            'sub_total': first_item.sub_total,
            'rejection_reason': first_item.rejection_reason if first_item.status == "rejected" else None
        })

    # Sort by most recent date
    grouped_notifications.sort(key=lambda x: x['created_at'] if x['created_at'] else datetime.min, reverse=True)

    # Format times to HH:MM:SS
    current_time = datetime.now().strftime("%H:%M:%S")
    opening_time = business.opening_time.strftime("%H:%M:%S") if business and business.opening_time else "00:00:00"
    closing_time = business.closing_time.strftime("%H:%M:%S") if business and business.closing_time else "23:59:59"

    return render(request, 'MSMEOrderingWebApp/customer_notification.html', {
        'notifications': grouped_notifications,
        'business': business,
        'customization': customization,
        'current_time': current_time,
        'opening_time': opening_time,
        'closing_time': closing_time,
    })

@login_required_session(allowed_roles=['customer'])
def partial_customer_notifications(request):
    customization = get_or_create_customization()
    email = request.session.get('email')
    business = BusinessDetails.objects.first()

    # Group by both order_code AND date
    all_orders = Checkout.objects.filter(
        email=email,
        status__in=[
            "accepted", "rejected", "Preparing", "Packed",
            "Ready for Pickup", "Out for Delivery", "Completed", "Void", "delivered"
        ]
    ).order_by('-created_at')

    grouped = defaultdict(list)
    for order in all_orders:
        # Create composite key with order_code + date
        order_date = order.created_at.date() if order.created_at else None
        composite_key = f"{order.order_code}_{order_date}" if order_date else order.order_code
        grouped[composite_key].append(order)

    # Convert to display format
    grouped_notifications = []
    for composite_key, items in grouped.items():
        # Extract clean order code for display
        clean_order_code = composite_key.split('_')[0] if '_' in composite_key else composite_key
        first_item = items[0]
        grouped_notifications.append({
            'order_code': clean_order_code,
            'status': first_item.status,
            'created_at': first_item.created_at,
            'items': items,
            'sub_total': first_item.sub_total,
            'rejection_reason': first_item.rejection_reason if first_item.status == "rejected" else None,
			'void_reason': first_item.void_reason if first_item.status.lower() == "void" else None,
            'order_type': first_item.order_type,
            'delivery_fee': first_item.delivery_fee,
            'final_total': (first_item.sub_total + first_item.delivery_fee) if first_item.order_type and first_item.order_type.lower() == "delivery" and first_item.delivery_fee else first_item.sub_total,
        })

    # Sort by most recent date
    grouped_notifications.sort(key=lambda x: x['created_at'] if x['created_at'] else datetime.min, reverse=True)

    # Format times to HH:MM:SS
    current_time = datetime.now().strftime("%H:%M:%S")
    opening_time = business.opening_time.strftime("%H:%M:%S") if business and business.opening_time else "00:00:00"
    closing_time = business.closing_time.strftime("%H:%M:%S") if business and business.closing_time else "23:59:59"

    html = render_to_string("partials/customer_notifications_list.html", {
        'notifications': grouped_notifications,
        'customization': customization,
        'business': business,
        'current_time': current_time,
        'opening_time': opening_time,
        'closing_time': closing_time,
    })
    return HttpResponse(html)

def notify_customer(email, message):
    group = f"customer_{email.replace('@', '_at_').replace('.', '_dot_')}"
    
    # Count unique order_code + date combinations for accurate badge count
    all_orders = Checkout.objects.filter(
        email=email,
        status__in=["accepted", "rejected"]
    )
    
    unique_orders = set()
    for order in all_orders:
        order_date = order.created_at.date() if order.created_at else None
        composite_key = f"{order.order_code}_{order_date}" if order_date else order.order_code
        unique_orders.add(composite_key)
    
    customer_count = len(unique_orders)

    async_to_sync(get_channel_layer().group_send)(
        group,
        {
            "type": "send_customer_notification",
            "message": message,
            "customer_count": customer_count,
        }
    )

    

@login_required_session(allowed_roles=['customer'])
def customer_profile(request):
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)

    business = BusinessDetails.objects.first()
    customization = get_or_create_customization()
    edit_mode = request.GET.get('edit', False)

    # Group orders by both order_code AND date
    raw_orders = Checkout.objects.filter(email=user.email).order_by('-created_at')
    grouped_orders = defaultdict(list)
    
    for order in raw_orders:
        # Create a composite key: order_code + date (YYYY-MM-DD) for grouping
        order_date = order.created_at.date() if order.created_at else None
        composite_key = f"{order.order_code}_{order_date}" if order_date else order.order_code
        grouped_orders[composite_key].append(order)
    
    # Convert to list of tuples with clean order_code for display
    display_orders = []
    for composite_key, items in grouped_orders.items():
        # Extract the original order_code (everything before the first underscore)
        clean_order_code = composite_key.split('_')[0] if '_' in composite_key else composite_key
        display_orders.append((clean_order_code, items))
    
    # Sort by most recent date
    display_orders.sort(key=lambda x: x[1][0].created_at if x[1][0].created_at else datetime.min, reverse=True)

    if request.method == 'POST':
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.contact_number = request.POST.get('contact_number')
        user.address = request.POST.get('address')
        user.city = request.POST.get('city')
        user.province = request.POST.get('province')
        user.zipcode = request.POST.get('zipcode')

        if 'profile_image' in request.FILES:
            user.image = request.FILES['profile_image']

        user.save()
        return redirect('customer_profile')

    # Format times to HH:MM:SS
    current_time = datetime.now().strftime("%H:%M:%S")
    opening_time = business.opening_time.strftime("%H:%M:%S") if business and business.opening_time else "00:00:00"
    closing_time = business.closing_time.strftime("%H:%M:%S") if business and business.closing_time else "23:59:59"

    return render(request, 'MSMEOrderingWebApp/customer_profile.html', {
        'user_data': user,
        'customization': customization,
        'business': business,
        'edit_mode': edit_mode,
        'grouped_orders': display_orders,
        'current_time': current_time,
        'opening_time': opening_time,
        'closing_time': closing_time,
    })

@login_required_session(allowed_roles=['owner'])
def online_payment_details(request):
    customization = get_or_create_customization()
    business = BusinessDetails.objects.first()
    all_payments = OnlinePaymentDetails.objects.all().order_by('-id')
    selected_payment = None

    if request.method == 'POST':
        payment_id = request.POST.get('payment_id')

        if 'save' in request.POST:
            bank_name = request.POST.get('bank_name')
            recipient_name = request.POST.get('recipient_name')
            phone_number = request.POST.get('phone_number')
            qr_image = request.FILES.get('qr_image')

            if payment_id:
                try:
                    payment = OnlinePaymentDetails.objects.get(id=payment_id)
                    payment.bank_name = bank_name
                    payment.recipient_name = recipient_name
                    payment.phone_number = phone_number
                    if qr_image:
                        payment.qr_image = qr_image
                    payment.save()
                except OnlinePaymentDetails.DoesNotExist:
                    pass
            else:
                OnlinePaymentDetails.objects.create(
                    bank_name=bank_name,
                    recipient_name=recipient_name,
                    phone_number=phone_number,
                    qr_image=qr_image
                )

        elif 'edit' in request.POST and payment_id:
            try:
                selected_payment = OnlinePaymentDetails.objects.get(id=payment_id)
            except OnlinePaymentDetails.DoesNotExist:
                selected_payment = None

        elif 'delete' in request.POST and payment_id:
            try:
                OnlinePaymentDetails.objects.get(id=payment_id).delete()
            except OnlinePaymentDetails.DoesNotExist:
                pass

        return redirect('online_payment_details')  # URL name must match urls.py

    context = {
        'customization': customization,
        'payment_details': selected_payment,
        'all_payments': all_payments,
        'title': 'Set Up Payment Details',
        'business': business    
    }
    return render(request, 'MSMEOrderingWebApp/onlinepayment_details.html', context)


@login_required_session(allowed_roles=['owner'])
def delete_online_payment(request, id):
    obj = get_object_or_404(OnlinePaymentDetails, id=id)
    obj.delete()
    return redirect('online_payment_details')

@login_required_session(allowed_roles=['customer'])
def customer_viewonlinepayment(request):
    customization = get_or_create_customization()
    payment_methods = OnlinePaymentDetails.objects.all().order_by('-id')
    business = BusinessDetails.objects.first()

    return render(request, 'MSMEOrderingWebApp/customer_viewonlinepayment.html', {
        'customization': customization,
        'payment_methods': payment_methods,
        'business': business,
    })

@login_required_session(allowed_roles=['owner'])
def business_viewonlinepayment(request):
    customization = get_or_create_customization()
    payment_methods = OnlinePaymentDetails.objects.all().order_by('-id')
    business = BusinessDetails.objects.first()

    return render(request, 'MSMEOrderingWebApp/business_viewonlinepayment.html', {
        'customization': customization,
        'payment_methods': payment_methods,
        'business': business,
		'title':'Online Payment Details'
    })

@login_required_session(allowed_roles=['cashier'])
def cashier_viewonlinepayment(request):
    customization = get_or_create_customization()
    payment_methods = OnlinePaymentDetails.objects.all().order_by('-id')
    business = BusinessDetails.objects.first()

    return render(request, 'MSMEOrderingWebApp/cashier_viewonlinepayment.html', {
        'customization': customization,
        'payment_methods': payment_methods,
        'business': business,
		'title':'Online Payment Details'
    })
	
@login_required_session(allowed_roles=['owner'])
def business_changepassword(request):
    owner_id = request.session.get('owner_id')
    owner = get_object_or_404(BusinessOwnerAccount, id=owner_id)

    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        # Check if current password is correct
        if current_password != owner.password:
            return JsonResponse({'success': False, 'message': "Current password is incorrect."})

        # Check if new password matches confirm password
        if new_password != confirm_password:
            return JsonResponse({'success': False, 'message': "New password and confirmation do not match."})

        # Check password strength
        import re
        pattern = r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$'
        if not re.match(pattern, new_password):
            return JsonResponse({'success': False, 'message': "Password must be at least 8 characters long, include letters, numbers, and a special character."})

        # Update password
        owner.password = new_password
        owner.save()
        return JsonResponse({'success': True, 'message': "Password changed successfully."})

    return render(request, 'MSMEOrderingWebApp/business_changepassword.html')



@login_required_session(allowed_roles=['customer'])
def customer_changepassword(request):
    user_id = request.session.get('user_id')
    user = User.objects.get(id=user_id)

    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        # Validate current password
        if user.password != current_password:
            return JsonResponse({'status': 'error', 'message': 'Current password is incorrect.'})

        # Validate new password match
        if new_password != confirm_password:
            return JsonResponse({'status': 'error', 'message': 'New passwords do not match.'})

        # Prevent reuse of old password
        if new_password == current_password:
            return JsonResponse({'status': 'error', 'message': 'New password cannot be the same as current password.'})

        # Validate password requirements
        password_pattern = r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[!@#$%^&*]).{8,}$'
        if not re.match(password_pattern, new_password):
            return JsonResponse({
                'status': 'error',
                'message': 'Password must be at least 8 characters long, include letters, numbers, and a special character (!@#$%^&*).'
            })

        # Save the new password (still plain text in your setup)
        user.password = new_password
        user.save()

        return JsonResponse({'status': 'success', 'message': 'Password changed successfully.'})

    # If not AJAX or not POST
    return JsonResponse({'status': 'error', 'message': 'Invalid request.'})

@login_required_session(allowed_roles=['customer'])
def add_to_cart(request):
    print("add_to_cart called")
    if request.method == 'POST':
        print("POST request received")
        if 'user_id' not in request.session or request.session.get('user_type') != 'customer':
            return JsonResponse({'success': False, 'error': 'User not authenticated'})

        try:
            data = json.loads(request.body)

            user_id = request.session.get('user_id')
            user = User.objects.get(id=user_id)

            # Extract product_name and variation_name
            full_name = data.get('product_name')  # e.g., "Ember Lulu - small (₱100.00)"
            match = re.match(r"^(.*?)\s*-\s*(.*?)\s*\(₱.*?\)$", full_name)
            if match:
                product_name = match.group(1).strip()
                variation_name = match.group(2).strip()
            else:
                product_name = full_name
                variation_name = "Default"

            # Try to fetch product from DB
            product = None
            image_file = None
            try:
                product = Products.objects.get(name=product_name, variation_name=variation_name)
                if product.image:
                    image_file = product.image  # ✅ use existing product image
            except Products.DoesNotExist:
                pass

            # If frontend sent an image URL and no DB image, use that instead
            if not image_file:
                image_url = data.get("image")
                if image_url:
                    try:
                        response = requests.get(image_url, timeout=5)
                        if response.status_code == 200:
                            filename = os.path.basename(urlparse(image_url).path) or "cart_image.jpg"
                            image_file = ContentFile(response.content, name=filename)
                    except Exception as e:
                        print("Image fetch failed:", e)

            # Compose full address
            full_address = f"{user.address}, {user.city}, {user.province}"
            print("Full address to save:", full_address)

            # Save to cart
            Cart.objects.create(
                first_name=user.first_name,
                last_name=user.last_name,
                contact_number=user.contact_number,
                address=full_address,
                email=user.email,
                product_name=full_name,
                quantity=data.get('quantity'),
                price=data.get('price'),
                image=image_file  # ✅ final image
            )

            return JsonResponse({'success': True})

        except Exception as e:
            print("Error in add_to_cart:", e)
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})




@csrf_exempt
def forgot_password(request):
    customization = get_or_create_customization()
    if request.method == 'POST':
        email = request.POST.get('email')

        # Check if the email exists in any of the tables
        user = None
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
        elif BusinessOwnerAccount.objects.filter(email=email).exists():
            user = BusinessOwnerAccount.objects.get(email=email)
        elif StaffAccount.objects.filter(email=email).exists():  # ✅ Added Staff check
            user = StaffAccount.objects.get(email=email)

        if user:
            otp_code = str(random.randint(100000, 999999))  # store as string
            otp, created = OTP.objects.update_or_create(
                email=email,
                defaults={'otp': otp_code, 'created_at': now()}
            )

            from django.core.mail import EmailMultiAlternatives
from django.conf import settings as django_settings
from django.http import JsonResponse
from django.utils.timezone import now
import random

def forgot_password(request):
    BusinessDetails_obj = BusinessDetails.objects.first()
    customization = get_or_create_customization()

    if request.method == 'POST':
        email = request.POST.get('email')

        # Check if the email exists in any of the tables
        user = None
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
        elif BusinessOwnerAccount.objects.filter(email=email).exists():
            user = BusinessOwnerAccount.objects.get(email=email)
        elif StaffAccount.objects.filter(email=email).exists():  # ✅ Added Staff check
            user = StaffAccount.objects.get(email=email)

        if user:
            otp_code = str(random.randint(100000, 999999))  # store as string
            otp, created = OTP.objects.update_or_create(
                email=email,
                defaults={'otp': otp_code, 'created_at': now()}
            )

            # ✅ Prepare email body for staff OTP verification
            body = f"""
<html>
<head>
    <!-- Montserrat font -->
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap" rel="stylesheet">
</head>
<body style="
    font-family: 'Montserrat', Arial, sans-serif;
    background: linear-gradient(135deg, {customization.primary_color or '#0F0F0F'} 50%, {customization.secondary_color or '#555555'} 100%);
    margin: 0;
    padding: 40px 0;
    color: #fff;
">

    <!-- Container with blur and low opacity -->
    <div style="
        max-width: 600px;
        margin: 0 auto;
        background: rgba(17,17,17,0.35);
        border-radius: 20px;
        padding: 40px;
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 8px 32px rgba(0,0,0,0.7);
        backdrop-filter: blur(55px);
        -webkit-backdrop-filter: blur(20px);
        position: relative;
    ">

        <!-- Header -->
        <div style="text-align: center; margin-bottom: 15px;">
            <h1 style="
                font-size: 28px;
                font-weight: 700;
                margin: 0;
                color: #FFFFFF;
            ">
                PASSWORD RESET REQUEST
            </h1>
        </div>

        <!-- Body -->
        <div style="
            text-align: center;
            font-size: 16px;
            line-height: 1.6;
            color: #ffffff;
        ">
            <p style="margin-bottom: 10px;">To reset your password, use the OTP below:</p>
            <div style="
                font-size: 36px;
                font-weight: 800;
                color: #ffffff;
                margin-bottom: 20px;
            ">
                {otp_code}
            </div>
        </div>

        <!-- Info / Footer Note -->
        <div style="
            text-align: center;
            font-size: 14px;
            color: rgba(255,255,255,0.95);
        ">
            If you didn't request a password reset, please ignore this email.
        </div>

        <!-- Divider -->
        <div style="
            margin: 20px auto;
            width: 50px;
            height: 2px;
            background: #fff;
            border-radius: 2px;
        "></div>

        <!-- Footer -->
        <div style="font-size: 13px; text-align: center; margin: 0;">
            © 2025 Online Ordering System
        </div>    

    </div>
</body>
</html>
"""
            try:
                # ✅ Use Django email system
                email_message = EmailMultiAlternatives(
                    subject="Your OTP for Password Reset",
                    body=f"Your OTP is {otp_code}",  # plain text fallback
                    from_email=django_settings.EMAIL_HOST_USER,
                    to=[email],
                )
                email_message.attach_alternative(body, "text/html")
                email_message.send()

                return JsonResponse({'status': 'success', 'message': 'OTP sent to your email.'})

            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'Failed to send email: {str(e)}'}, status=500)

        return JsonResponse({'status': 'error', 'message': 'Email not found.'}, status=404)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=400)


@csrf_exempt
def forgot_passwordotp(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        otp_code = request.POST.get('otp_code')

        try:
            otp = OTP.objects.get(email=email, otp=otp_code)
            return JsonResponse({'status': 'success', 'message': 'OTP verified.'})
        except OTP.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Invalid OTP.'}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=400)


@csrf_exempt
def forgot_password_reset(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        new_password = request.POST.get('newPassword')
        confirm_password = request.POST.get('confirmPassword')

        # Password match check
        if new_password != confirm_password:
            return JsonResponse({'status': 'error', 'message': 'Passwords do not match.'}, status=400)

        # Password requirement check
        if not re.match(r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', new_password):
            return JsonResponse({
                'status': 'error',
                'message': 'Password must be at least 8 characters long, include a letter, a number, and a special character.'
            }, status=400)

        # Check user across all account types
        user = None
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
        elif BusinessOwnerAccount.objects.filter(email=email).exists():
            user = BusinessOwnerAccount.objects.get(email=email)
        elif StaffAccount.objects.filter(email=email).exists():  # ✅ Added Staff support
            user = StaffAccount.objects.get(email=email)

        if user:
            user.password = new_password  # ⚠️ You might want to hash this before saving!
            user.save()
            OTP.objects.filter(email=email).delete()
            return JsonResponse({'status': 'success', 'message': 'Password updated successfully.'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Email not found.'}, status=404)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=400)

    
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from .models import CustomerReview
from django.utils import timezone

@login_required_session(allowed_roles=['owner'])
def update_review_response(request, review_id):
    if request.method == 'POST':
        try:
            review = CustomerReview.objects.get(pk=review_id)
            review.owner_response = request.POST.get('owner_response')
            review.response_date = timezone.now()
            review.save()
            return JsonResponse({'status': 'success'})
        except CustomerReview.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Review not found.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

@login_required_session(allowed_roles=['owner'])
def hide_review(request, review_id):
    if request.method == 'POST':
        try:
            review = CustomerReview.objects.get(pk=review_id)
            review.is_hidden = True
            review.save()
            return JsonResponse({'status': 'success'})
        except CustomerReview.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Review not found.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid method'})

@login_required_session(allowed_roles=['owner'])
def show_review(request, review_id):
    if request.method == 'POST':
        try:
            review = CustomerReview.objects.get(pk=review_id)
            review.is_hidden = False
            review.save()
            return JsonResponse({'status': 'success'})
        except CustomerReview.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Review not found.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid method'})
