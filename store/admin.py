from django import forms
from django.contrib import admin
from ckeditor.widgets import CKEditorWidget

from store.models import Group, Category, Product, Order, \
    OrderProduct, Article, Customer


class ProductAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Товар',
         {'fields': ['article', 'title', 'category', 'price',
                     ('warehouse1', 'warehouse2'),
                     ('image', 'image_thumb',), 'display', ]}
         ),
    ]
    readonly_fields = ['article', 'title', 'category', 'image_thumb', 'price',
                       'warehouse1', 'warehouse2', ]
    list_display = ('article', 'title', 'quantity', 'image_thumb',
                    'category', 'price', 'display')
    list_filter = ['display', 'category', ]
    search_fields = ['article', 'title']
    ordering = ('title', 'category', 'price')


class CategoryProductInline(admin.TabularInline):
    model = Product
    fields = ['article', 'title', 'image_thumb', 'price', 'warehouse1', 'warehouse2', ]
    readonly_fields = ['article', 'title', 'image_thumb', 'price', 'warehouse1', 'warehouse2', ]
    can_delete = False
    extra = 0


class CategoryAdmin(admin.ModelAdmin):
    fields = ['name', 'parent', ('image', 'image_thumb'), ]
    readonly_fields = ['image_thumb']
    list_display = ('name', 'image_thumb', 'parent',)
    list_filter = ['parent']
    # inlines = [CategoryProductInline]
    # CategoryProductInline.verbose_name = 'Товар'


class GroupCategoryInline(admin.TabularInline):
    model = Category
    fields = ['id', 'name', ]
    readonly_fields = ['id', 'name', ]
    can_delete = False
    extra = 0
    max_num = 0
    show_change_link = True


class GroupAdmin(admin.ModelAdmin):
    fields = ['name', ('image', 'image_thumb'), 'start_page', ]
    readonly_fields = ['image_thumb', ]
    list_display = ('name', 'image_thumb', 'start_page')
    # inlines = [GroupCategoryInline]
    # GroupCategoryInline.verbose_name = 'Категория'


class CustomerOrderInLine(admin.TabularInline):
    model = Order
    fields = ['id', 'created_at', 'status', 'total_products', 'products', 'total_price_net']
    readonly_fields = ['id', 'created_at', 'total_products', 'products', 'total_price_net']
    can_delete = False
    max_num = 0
    extra = 0
    show_change_link = True


class CustomerAdmin(admin.ModelAdmin):
    fields = ['user', 'email', 'last_name', ('first_name', 'patronymic'), 'phone', 'is_confirmed']
    readonly_fields = ['user', 'email', 'first_name', 'last_name', 'patronymic', 'phone', 'is_confirmed', ]
    list_display = ('user', 'phone', 'email', 'get_fio', 'created', 'is_confirmed')
    list_filter = ['is_confirmed', 'created']
    search_fields = ['last_name', 'phone']
    ordering = ('-created',)
    inlines = [CustomerOrderInLine]


class OrderItemInline(admin.TabularInline):
    model = OrderProduct
    fields = ['product', 'image_thumb', 'qty', 'final_price', ]
    readonly_fields = ['product', 'image_thumb', 'qty', 'final_price', ]
    can_delete = False
    extra = 0
    max_num = 0
    # raw_id_fields = ['product']


class OrderAdmin(admin.ModelAdmin):
    fields = ('last_name', ('first_name', 'patronymic'), 'owner',
              'created_at', 'phone', 'comment', 'total_price_net',
              'status', 'remark',)
    readonly_fields = ['first_name', 'last_name', 'patronymic', 'phone',
                       'created_at', 'comment', 'owner', 'total_price_net', ]
    list_display = ('id', 'status', 'total_products', 'get_fio', 'created_at')
    list_display_links = ('id', 'status')
    search_fields = ['last_name', 'phone']
    ordering = ('-created_at', 'owner', 'status',)
    list_filter = ('status', 'created_at',)
    inlines = [OrderItemInline]


class ArticleAdminForm(forms.ModelForm):
    title = forms.CharField(label='Заголовок', max_length=200)
    content = forms.CharField(label='Текст страницы', widget=CKEditorWidget())


class ArticleAdmin(admin.ModelAdmin):
    form = ArticleAdminForm

    fieldsets = (
        (None, {'fields': ('slug', 'name', 'title', 'content',)}),
    )
    list_display = ('name', 'title', 'slug',)


admin.site.site_header = "Панель управления магазина Электр{он/ика}"
# admin.site.unregister(Group)
admin.site.register(Group, GroupAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Article, ArticleAdmin)

admin.site.register(Customer, CustomerAdmin)
