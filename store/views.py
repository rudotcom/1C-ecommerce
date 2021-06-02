from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.views.generic import DetailView, View, ListView
from django.urls import reverse

from ecommerce import settings
from .forms import LoginForm, RegistrationForm, OrderForm
from .mixins import CartMixin
from .models import Group, Category, Customer, OrderProduct, \
    Product, Order, Article
from .tasks import send_confirmation_email, send_order_email, \
    send_order_personnel_email
from .utils import get_random_session


class MyQ(Q):
    default = 'OR'


class WelcomeView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        groups = Group.objects.filter(start_page=True).order_by('name')
        count = Group.objects.all().count()

        context = {
            'groups': groups,
            'count': count,
            'cart': self.cart,
            'articles': self.articles,
        }
        return render(request, 'favourites_list.html', context)


class GroupListView(CartMixin, View):
    model = Group

    def get(self, request, *args, **kwargs):
        groups = Group.objects.all().order_by('name')

        context = {
            'groups': groups,
            'cart': self.cart,
            'articles': self.articles,
        }
        return render(request, 'group_list.html', context)


class ProductDetailView(CartMixin, DetailView):
    model = Product
    template_name = 'item_detail.html'

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context['cart'] = self.cart
        context['articles'] = self.articles

        return context


class ProductListView(CartMixin, ListView):
    model = Product
    template_name = 'product_list.html'
    paginate_by = 50

    def get_queryset(self):
        pk = self.kwargs.get('pk')
        object_list = Product.objects.filter(category_id=pk)
        return object_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cart'] = self.cart
        context['articles'] = self.articles
        context['category'] = Category.objects.get(pk=self.kwargs.get('pk'))

        view = self.request.GET.get('view') \
               or self.request.session.get('view') or 'list'
        if view:
            self.request.session['view'] = view
        context['view'] = view

        pager = self.paginate_by or int(self.request.session.get('pager'))
        context['pager'] = pager
        if pager:
            self.request.session['pager'] = pager

        return context

    def get_paginate_by(self, queryset):
        pager = int(self.request.GET.get('pager') or 0) \
                or self.request.session.get('pager')
        if pager:
            self.request.session['pager'] = pager
            self.paginate_by = pager
        return pager


class GroupDetailView(CartMixin, DetailView):
    model = Group
    queryset = Group.objects.all()
    context_object_name = 'group'
    template_name = 'category_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = self.get_object()
        context['cart'] = self.cart
        context['group_name'] = group.name
        context['categories'] = Category.objects.filter(
            parent=group
        ).order_by('name')
        context['articles'] = self.articles
        return context


class ProductSearchView(CartMixin, ListView):
    model = Product
    template_name = 'product_search.html'
    paginate_by = 50

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('p')
        context['query'] = query
        context['cart'] = self.cart
        context['articles'] = self.articles

        view = self.request.GET.get('view') or self.request.session.get('view')
        if view:
            self.request.session['view'] = view
        context['view'] = view

        pager = self.paginate_by or self.request.session.get('pager')
        context['pager'] = pager
        if pager:
            self.request.session['pager'] = pager
        return context

    def get_queryset(self):
        query = self.request.GET.get('p')
        object_list = Product.objects.filter(
            Q(title__icontains=query) | Q(article__icontains=query)
        )
        return object_list

    def get_paginate_by(self, queryset):
        pager = self.request.GET.get('pager') or self.request.session.get('pager')
        if pager:
            self.request.session['pager'] = pager
            self.paginate_by = pager
        return pager


class AddToCartView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        if request.user.groups.filter(name='Персонал').exists():
            return HttpResponseRedirect(reverse('admin:store_product_change', args=(kwargs['pk'],)))
        # Определяем, существует ли корзина, или создаем ее
        if not self.cart:
            # если нет, создаем ее id в сессии
            cart = get_random_session()
            self.cart, created = Order.carts.get_or_create(session=cart)
            self.request.session['cart'] = cart

            if created:
                # Это создание новой корзины. Удалить анонимные корзины старше 2 дней
                old_carts = Order.carts.filter(
                    created_at__lte=datetime.now() - timedelta(days=2)
                ).delete()

        try:
            customer = Customer.objects.get(user=request.user)
            self.cart.owner = customer
            self.cart.save()
        except Exception:
            print('Anonimous cart')

        product = Product.objects.get(pk=kwargs['pk'])
        if product.quantity:
            order_product, created = OrderProduct.objects.get_or_create(
                order=self.cart, product=product
            )

            if created:
                self.cart.products.add(order_product)
                messages.add_message(
                    request,
                    messages.INFO,
                    f'{order_product.product.image_thumb()}'
                    f'Добавлено в корзину: <b>{order_product.product}</b> '
                )
            else:
                if order_product.product.quantity <= order_product.qty:
                    message = f'{order_product.product.image_thumb()}' \
                              f' Количество товара <b>{order_product}</b> ' \
                              f'в корзине {order_product.qty} шт.<br> ' \
                              f'На складе больше нет, извините!'
                    order_product.qty = order_product.product.quantity
                else:
                    order_product.qty += 1
                    message = f'{order_product.product.image_thumb()} ' \
                              f'Количество товара <b>{order_product}</b> ' \
                              f'изменено на {order_product.qty} шт.'

                order_product.save()
                messages.add_message(
                    request,
                    messages.INFO,
                    message
                )
            self.cart.save()

        response = HttpResponseRedirect(reverse('cart'))
        return response


class DeleteFromCartView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        product = Product.objects.get(pk=kwargs['pk'])
        order_product = OrderProduct.objects.get(
            order=self.cart, product=product
        )

        self.cart.products.remove(order_product)
        order_product.delete()
        self.cart.save()
        messages.add_message(request, messages.INFO,
                             f'{order_product.product.image_thumb()} '
                             f' Удалено из корзины: <b>{order_product}</b>')
        return HttpResponseRedirect(reverse('cart'))


class ChangeQTYView(CartMixin, View):

    def post(self, request, *args, **kwargs):
        product = Product.objects.get(pk=kwargs['pk'])
        order_product = OrderProduct.objects.get(
            order=self.cart, product=product
        )
        qty = int(request.POST.get('qty'))
        over = False
        if order_product.product.quantity < qty:
            over = True
            qty = order_product.product.quantity

        if qty:
            order_product.qty = qty
            message = f'{order_product.product.image_thumb()} ' \
                      f'Количество товара <b>{order_product}</b> ' \
                      f'изменено на {qty} шт.'
            if over:
                message += '<br>На складе больше нет, извините!'
            messages.add_message(
                request,
                messages.INFO,
                message
            )
            order_product.save()
        else:
            self.cart.products.remove(order_product)
            order_product.delete()
            messages.add_message(
                request,
                messages.INFO,
                f'{order_product.product.image_thumb()} '
                f'Удалено из корзины: <b>{order_product}</b>'
            )
        self.cart.save()
        return HttpResponseRedirect(reverse('cart'))


class CartView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        if not self.cart or not self.cart.products.count():
            messages.add_message(
                request,
                messages.INFO,
                'Ваша корзина пуста!<br><a href=/store/>'
                'Посмотрите наши товары</a>'
            )

        # Заполняем форму данными покупателя, если есть
        if request.user.is_authenticated:
            customer = Customer.objects.get(user=request.user)
            form = OrderForm(instance=customer)
        else:
            form = OrderForm()

        context = {
            'form': form,
            'cart': self.cart,
            'articles': self.articles,
        }
        return render(request, 'cart.html', context)


class MakeOrderView(LoginRequiredMixin, CartMixin, View):
    login_url = '/login/'

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        form = OrderForm(request.POST or None)

        user = User.objects.get(username=request.user)
        customer = Customer.objects.get(user=user.id)

        if not customer.is_confirmed:
            context = {
                'cart': self.cart,
                'articles': self.articles,
            }
            return render(request, 'registration_confirmation_required.html', context=context)

        order = Order.carts.get(owner=customer)

        if form.is_valid():
            order.last_name = form.cleaned_data['last_name']
            order.first_name = form.cleaned_data['first_name']
            order.phone = form.cleaned_data['phone']
            order.comment = form.cleaned_data['comment']

            customer.last_name = form.cleaned_data['last_name']
            customer.first_name = form.cleaned_data['first_name']
            customer.phone = form.cleaned_data['phone']
            if 'patronymic' in form.cleaned_data.keys():
                order.patronymic = form.cleaned_data['patronymic']
                customer.patronymic = form.cleaned_data['patronymic']
        order.status = 'new'
        order.save()
        customer.save()

        messages.add_message(
            request,
            messages.INFO,
            'Ваш заказ оформлен! \nСпасибо, что выбрали нас.\n'
            f'Номер заказа {order.id}'
        )

        try:
            send_order_email(user.email, order)
            send_order_personnel_email(order)
        except Exception:
            messages.add_message(
                request, messages.INFO,
                f'Ошибка отправки почтовых сообщения \n'
                f'Почтовая служба недоступна.'
            )

        url = reverse('order', args=(order.id, ))
        response = HttpResponseRedirect(url)
        return response


class OrderView(LoginRequiredMixin, CartMixin, View):
    login_url = '/login/'

    def get(self, request, *args, **kwargs):
        if request.user.groups.filter(name='Персонал').exists():
            return HttpResponseRedirect(reverse('admin:store_order_change', args=(kwargs['pk'],)))

        user = User.objects.get(username=request.user)
        order_id = self.kwargs.get('pk')

        try:
            # Отображать заказ только если он принадлежит клиенту -
            # текущему пользователю
            order_detail = Order.orders.get(id=order_id, owner__user=user)

            return render(
                request,
                'store/order_detail.html',
                {
                    'cart': self.cart,
                    'order_detail': order_detail,
                    'articles': self.articles,
                }
            )
        except Exception:
            messages.add_message(
                request, messages.INFO,
                f'Заказа № {order_id} у вас нет! \n'
                f'Выберите свой заказ из списка.'
            )
            return HttpResponseRedirect(reverse('profile'))


class LoginView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        form = LoginForm(request.POST or None)

        context = {
            'form': form,
            'cart': self.cart,
            'articles': self.articles,
        }
        return render(request, 'login.html', context)

    def post(self, request, *args, **kwargs):

        next = request.GET['next'] if request.GET else reverse('profile')

        form = LoginForm(request.POST or None)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(
                username=username, password=password
            )
            if user:
                customer, created = Customer.objects.get_or_create(
                    user=user,
                )
                customer.save()
                # Удаляем корзины, если были созданы ранее
                Order.carts.filter(owner=customer).delete()
                # Присваиваем текущую корзину
                if self.cart:
                    self.cart.owner = customer


                login(request, user)
                return HttpResponseRedirect(next)

        context = {
            'form': form,
            'cart': self.cart,
            'articles': self.articles,
        }
        return render(request, 'login.html', context)


class RegistrationView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        form = RegistrationForm(request.POST or None)

        context = {
            'form': form,
            'cart': self.cart,
            'articles': self.articles,
        }
        return render(request, 'registration.html', context)

    def post(self, request, *args, **kwargs):

        form = RegistrationForm(request.POST or None)
        if form.is_valid():
            new_user = form.save(commit=False)
            new_user.email = form.cleaned_data['email']
            new_user.set_password(form.cleaned_data['password'])
            new_user.save()
            user = authenticate(
                username=new_user.username,
                password=form.cleaned_data['password']
            )
            login(request, user)
            customer, created = Customer.objects.get_or_create(user=new_user)
            customer.code = get_random_session()
            customer.save()

            try:
                send_confirmation_email(user.email, customer.code)
            except Exception:
                messages.add_message(
                    request, messages.INFO,
                    f'Ошибка отправки почтового сообщения \n'
                    f'Почтовая служба недоступна.'
                )

            context = {
                'cart': self.cart,
                'articles': self.articles,
            }

            return render(request, 'registration_confirmation_required.html', context=context)

        context = {
            'form': form,
            'cart': self.cart,
            'articles': self.articles,
        }
        return render(request, 'registration.html', context)


class EmailConfirmationView(CartMixin, View):

    def get(self, request, *args, **kwargs):
        context = {
            'cart': self.cart,
            'page_role': 'registration',
            'articles': self.articles,
        }
        code = kwargs.get('code')
        try:
            customer = Customer.objects.get(code=code)
            customer.code = None
            customer.is_confirmed = True
            customer.save()
            return render(request, 'registration_confirmed.html', context)
        except:
            return render(request, 'registration_confirmation_failed.html', context)


class ProfileView(LoginRequiredMixin, CartMixin, View):
    login_url = '/login/'

    def get(self, request, *args, **kwargs):
        if request.user.groups.filter(name='Персонал').exists():
            return HttpResponseRedirect(reverse('admin:store_order_changelist'))

        customer = Customer.objects.get(user=request.user)
        orders = Order.orders.filter(owner=customer).order_by('-created_at')

        return render(
            request,
            'profile.html',
            {
                'customer': customer,
                'orders': orders,
                'cart': self.cart,
                'page_role': 'profile',
                'articles': self.articles,
            }
        )


class ArticleView(CartMixin, DetailView):
    model = Article
    context_object_name = 'article'
    template_name = 'article_detail.html'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cart'] = self.cart
        context['articles'] = self.articles

        return context


class EmailView(LoginRequiredMixin, CartMixin, View):
    login_url = '/login/'

    def get(self, request, *args, **kwargs):

        order_id = kwargs.get('cart')
        try:
            pay_order = Order.orders.get(id=order_id)

            return render(
                request,
                # 'email_order_placed.html',
                'email_confirm.html',
                {
                    'site_url': settings.SITE_URL,
                    'cart': pay_order,
                }
            )
        except Exception:
            return HttpResponse(status=404)
