from django.db.models.signals import post_save
from django.dispatch import receiver
from store.models import Order
from store.tasks import send_order_is_ready_email


@receiver(post_save, sender=Order)
def count_subcategory_items(sender, instance, **kwargs):
    if instance.status == 'is_ready':
        context = {
            'order': instance,
        }
        send_order_is_ready_email(instance)
