from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import Checkout
import json
from urllib.parse import parse_qs
import uuid

class PrintConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # You can put all desktop apps in a single group
        await self.channel_layer.group_add("printers", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("printers", self.channel_name)

    async def send_print_job(self, event):
        await self.send(text_data=json.dumps(event["data"]))

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("notifications", self.channel_name)
        await self.accept()

        data = await self.get_counts()
        await self.send(text_data=json.dumps({
            'type': 'send_notification',
            'count': data["unseen_count"],         # For badge
            'dashboard_count': data["pending_count"]  # For dashboard card
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("notifications", self.channel_name)

    async def send_pending_count(self, event):
        await self.send(text_data=json.dumps({
            'type': 'send_notification',
            'count': event.get('unseen_count', 0),  # Badge
            'dashboard_count': event['pending_count']  # Card
        }))

    @sync_to_async
    def get_counts(self):
        return {
            "pending_count": Checkout.objects.filter(status="pending").values("order_code").distinct().count(),
            "unseen_count": Checkout.objects.filter(status="pending", is_seen_by_owner=False).values("order_code").distinct().count()
        }
    
    # Safe no-op handlers
    async def delivery_fee_response(self, event):
        print(f"[NotificationConsumer] Ignoring delivery_fee_response: {event}")

    async def delivery_fee_rejected(self, event):
        print(f"[NotificationConsumer] Ignoring delivery_fee_rejected: {event}")



class CustomerNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = None
        query_params = parse_qs(self.scope['query_string'].decode())
        raw_email = query_params.get('email', [None])[0]

        if not raw_email:
            await self.close()
            return

        self.email = raw_email
        self.group_name = f"customer_{self.sanitize_email(raw_email)}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        count = await self.get_customer_notification_count()
        await self.send(text_data=json.dumps({
            'type': 'send_customer_notification',
            'customer_count': count
        }))

    def sanitize_email(self, email):
        return email.replace('@', '_at_').replace('.', '_dot_')

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_customer_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'send_customer_notification',
            'message': event['message'],
            'customer_count': event['customer_count'],
        }))

    @sync_to_async
    def get_customer_notification_count(self):
        return Checkout.objects.filter(
        email=self.email,
        status__in=["accepted", "rejected", "Preparing", "Packed", "Ready for Pickup", "Out for Delivery", "Completed"],
        is_seen_by_customer=False
    ).values("order_code").distinct().count()

    # Safe no-op handlers
    async def delivery_fee_response(self, event):
        print(f"[CustomerNotificationConsumer] Ignoring delivery_fee_response: {event}")

    async def delivery_fee_rejected(self, event):
        print(f"[CustomerNotificationConsumer] Ignoring delivery_fee_rejected: {event}")

class DeliveryFeeOwnerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print(f"[Owner] Connecting {self.channel_name}")
        await self.channel_layer.group_add("owners", self.channel_name)
        await self.accept()
        print(f"[Owner] Connected: {self.channel_name}")

    async def disconnect(self, close_code):
        print(f"[Owner] Disconnecting {self.channel_name}")
        await self.channel_layer.group_discard("owners", self.channel_name)
        print(f"[Owner] Disconnected: {self.channel_name}")

    async def receive(self, text_data):
        print(f"[Owner] Received raw text: {text_data}")
        data = json.loads(text_data)
        print(f"[Owner] Parsed data: {data}")

        action = data.get("action")

        if action == "send_fee":
            customer_email = data["customer_email"]
            fee = data["delivery_fee"]
            request_id = data.get("request_id")
            customer_group = f"customer_{self.sanitize_email(customer_email)}"

            print(f"[Owner] send_fee for request_id={request_id} fee={fee} -> customer_group={customer_group}")

            # Notify customer with same canonical request_id
            await self.channel_layer.group_send(
                customer_group,
                {
                    "type": "delivery_fee_response",
                    "delivery_fee": fee,
                    "request_id": request_id,
                }
            )

            # Notify all owners to close modal for this request_id
            await self.channel_layer.group_send(
                "owners",
                {
                    "type": "delivery_fee_resolved",
                    "request_id": request_id,
                    "status": "sent",
                }
            )

        elif action == "reject_fee":
            customer_email = data["customer_email"]
            reason = data.get("reason", "Delivery request rejected")
            request_id = data.get("request_id")
            customer_group = f"customer_{self.sanitize_email(customer_email)}"

            print(f"[Owner] reject_fee for request_id={request_id} reason={reason} -> customer_group={customer_group}")

            # Notify customer
            await self.channel_layer.group_send(
                customer_group,
                {
                    "type": "delivery_fee_rejected",
                    "reason": reason,
                    "request_id": request_id,
                }
            )

            # Notify all owners to close modal for this request_id
            await self.channel_layer.group_send(
                "owners",
                {
                    "type": "delivery_fee_resolved",
                    "request_id": request_id,
                    "status": "rejected",
                }
            )

    # Event forwarded from customer->owners group_send
    async def delivery_fee_request(self, event):
        # event expected to include: customer_email, order_details, request_id
        print(f"[Owner] Sending fee request event to websocket: {event}")
        await self.send(text_data=json.dumps({
            "type": "delivery_fee_request",
            "customer_email": event["customer_email"],
            "order_details": event["order_details"],
            "request_id": event.get("request_id"),
            "created_at": event.get("created_at"),
            "expires_at": event.get("expires_at"),
        }))

    # Handler to send resolved event to owners' websockets
    async def delivery_fee_resolved(self, event):
        print(f"[Owner] Broadcasting resolved to websocket: {event}")
        await self.send(text_data=json.dumps({
            "type": "delivery_fee_resolved",
            "request_id": event.get("request_id"),
            "status": event.get("status"),
        }))

    async def delivery_fee_rejected(self, event):
        # keep a handler if needed (owner side might ignore)
        print(f"[Owner] delivery_fee_rejected (owner handler) ignoring: {event}")

    def sanitize_email(self, email):
        return email.replace('@', '_at_').replace('.', '_dot_')


class DeliveryFeeCustomerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print("[Customer] Connecting")
        query_params = parse_qs(self.scope['query_string'].decode())
        self.customer_email = query_params.get('email', [None])[0]

        if not self.customer_email:
            print("[Customer] No email found, closing connection")
            await self.close()
            return

        self.group_name = f"customer_{self.sanitize_email(self.customer_email)}"
        print(f"[Customer] Adding to group: {self.group_name}")
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        print("[Customer] Connected")

    async def disconnect(self, close_code):
        print(f"[Customer] Disconnecting {self.channel_name}")
        if hasattr(self, 'group_name') and self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            print(f"[Customer] Removed from group: {self.group_name}")

    async def receive(self, text_data):
        print(f"[Customer] Received raw text: {text_data}")
        data = json.loads(text_data)
        print(f"[Customer] Parsed data: {data}")

        action = data.get("action")
        if action == "request_fee":
            # Ensure canonical request_id (generate if missing)
            request_id = data.get("request_id") or str(uuid.uuid4())
            customer_email = data.get("customer_email")
            order_details = data.get("order_details")

            print(f"[Customer] request_fee: request_id={request_id} customer_email={customer_email}")

            # Include a created_at/expires_at if you want timer sync server-side
            created_at = data.get("created_at")  # optional
            expires_at = data.get("expires_at")  # optional

            # Broadcast to all owners; include request_id so all owners get same id
            await self.channel_layer.group_send(
                "owners",
                {
                    "type": "delivery_fee_request",
                    "customer_email": customer_email,
                    "order_details": order_details,
                    "request_id": request_id,
                    "created_at": created_at,
                    "expires_at": expires_at,
                }
            )

    # Response from owners to customer (owner consumer group_send)
    async def delivery_fee_response(self, event):
        print(f"[Customer] Sending fee response event to websocket: {event}")
        await self.send(text_data=json.dumps({
            "type": "delivery_fee_response",
            "delivery_fee": event.get("delivery_fee"),
            "request_id": event.get("request_id"),
        }))

    async def delivery_fee_rejected(self, event):
        print(f"[Customer] Delivery fee rejected event to websocket: {event}")
        await self.send(text_data=json.dumps({
            "type": "delivery_fee_rejected",
            "reason": event.get("reason"),
            "request_id": event.get("request_id"),
        }))

    def sanitize_email(self, email):
        return email.replace('@', '_at_').replace('.', '_dot_')
