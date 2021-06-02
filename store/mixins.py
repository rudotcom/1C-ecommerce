from django.core.cache import cache
from django.views.generic import View
from django.contrib.auth import logout

from .models import Order, Customer, Article


class CartMixin(View):
    customer = None

    def __init__(self):
        super().__init__()
        self.articles = cache.get_or_set('article_menu',
                                         Article.objects.all(), timeout=600)

    def dispatch(self, request, *args, **kwargs):

        if request.user.is_authenticated:
            try:
                self.customer = Customer.objects.get(user=request.user)
            except:
                # Разлогиниться
                logout(request)

        try:
            self.cart = Order.carts.get(session=self.request.session.get('cart'))
            self.cart.owner = self.customer
            self.cart.save()
        except:
            self.cart = None

        # print('customer:', self.customer, 'cart:', self.cart)

        return super().dispatch(request, *args, **kwargs)


class RequiredFieldsMixin:

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        fields_required = getattr(self.Meta, 'fields_required', None)

        if fields_required:
            for key in self.fields:
                if key in fields_required:
                    self.fields[key].required = True
