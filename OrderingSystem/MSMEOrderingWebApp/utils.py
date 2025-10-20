def get_or_create_customization():
    # Your logic here, e.g.:
    from .models import CustomizationSettings
    obj, _ = CustomizationSettings.objects.get_or_create(id=1)
    return obj

from datetime import datetime, timedelta
from django.utils import timezone
from .models import BusinessDetails

def get_business_day_range():
    business = BusinessDetails.objects.first()
    if not business or not business.opening_time or not business.closing_time:
        # fallback to calendar day
        today = timezone.localtime()
        start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return start, end

    now = timezone.localtime()
    today = now.date()

    opening_time = business.opening_time
    closing_time = business.closing_time

    start = timezone.make_aware(datetime.combine(today, opening_time))
    end = timezone.make_aware(datetime.combine(today, closing_time))

    # Handle overnight case (e.g. 18:00 → 03:00 next day)
    if end <= start:
        end += timedelta(days=1)

    # If current time is after midnight but before closing, shift window back one day
    if now < start and now.time() < closing_time:
        start -= timedelta(days=1)
        end -= timedelta(days=1)

    return start, end