from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Checkout
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@receiver(post_save, sender=Checkout)
def notify_orders(sender, instance, **kwargs):
    channel_layer = get_channel_layer()

    # ✅ Dashboard: total pending orders (card) and unseen (badge)
    pending_count = Checkout.objects.filter(status="pending").values("order_code").distinct().count()
    unseen_count = Checkout.objects.filter(status="pending", is_seen_by_owner=False).values("order_code").distinct().count()

    # ✅ Send to business dashboard WebSocket group
    async_to_sync(channel_layer.group_send)(
        "notifications",
        {
            "type": "send_pending_count",
            "pending_count": pending_count,
            "unseen_count": unseen_count,
        }
    )

    # ✅ Handle customer notifications
    status_list = ["accepted", "rejected", "Preparing", "Packed", "Ready for Pickup", "Out for Delivery", "Completed"]

    customer_count = Checkout.objects.filter(
        email=instance.email,
        status__in=status_list,
        is_seen_by_customer=False
    ).values("order_code").distinct().count()

    sanitized_email = instance.email.replace("@", "_at_").replace(".", "_dot_")
    group_name = f"customer_{sanitized_email}"

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "send_customer_notification",
            "message": f"Your order has been {instance.status}",
            "customer_count": customer_count,
        }
    )
