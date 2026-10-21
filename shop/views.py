from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import role_required
from .forms import CategoryForm, CheckoutForm, NewsForm, OrderEditForm, ProductForm, RegisterForm
from .models import CartItem, Category, News, Order, OrderItem, Product, Role, UserProfile


class ShopLoginView(LoginView):
    template_name = 'shop/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, 'Вы вошли в магазин.')
        return super().form_valid(form)


def home(request):
    news = News.objects.all()[:3]
    featured = []
    for category in Category.objects.all():
        product = category.products.first()
        if product:
            featured.append(product)
    return render(request, 'shop/home.html', {'news': news, 'featured': featured})


def news_list(request):
    return render(request, 'shop/news_list.html', {'news': News.objects.all()})


def news_detail(request, pk):
    item = get_object_or_404(News, pk=pk)
    return render(request, 'shop/news_detail.html', {'item': item})


def contacts(request):
    return render(request, 'shop/contacts.html')


def catalog(request):
    categories = Category.objects.prefetch_related('products')
    return render(request, 'shop/catalog.html', {'categories': categories})


def category_detail(request, pk):
    category = get_object_or_404(Category, pk=pk)
    products = category.products.all()
    return render(request, 'shop/category.html', {'category': category, 'products': products})


def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
    related = Product.objects.filter(category=product.category).exclude(pk=product.pk)[:3]
    return render(request, 'shop/product.html', {'product': product, 'related': related})


def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        role = Role.objects.get(code='client')
        UserProfile.objects.create(user=user, role=role, phone=form.cleaned_data['phone'])
        login(request, user)
        messages.success(request, 'Регистрация завершена. Теперь вы клиент Komaru Tea.')
        return redirect('catalog')
    return render(request, 'shop/register.html', {'form': form})


@role_required('client')
def cart(request):
    items = CartItem.objects.filter(user=request.user).select_related('product')
    profile = request.user.profile
    form = CheckoutForm(
        request.POST or None,
        initial={'address': profile.address, 'phone': profile.phone},
    )
    if request.method == 'POST':
        if not items:
            messages.error(request, 'Корзина пуста.')
        elif form.is_valid():
            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    address=form.cleaned_data['address'],
                    phone=form.cleaned_data['phone'],
                    comment=form.cleaned_data['comment'],
                )
                for item in items:
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        product_name=item.product.name,
                        price=item.product.price,
                        quantity=item.quantity,
                    )
                items.delete()
                profile.address = order.address
                profile.phone = order.phone
                profile.save(update_fields=['address', 'phone'])
            messages.success(request, f'Заказ №{order.pk} оформлен.')
            return redirect('order_detail', pk=order.pk)
    total = sum((item.line_total for item in items), Decimal('0'))
    return render(request, 'shop/cart.html', {'items': items, 'form': form, 'total': total})


@role_required('client')
@require_POST
def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    try:
        qty = int(request.POST.get('quantity', '1'))
    except (TypeError, ValueError):
        qty = 1
    qty = max(1, min(qty, 20))
    item, created = CartItem.objects.get_or_create(
        user=request.user, product=product, defaults={'quantity': qty}
    )
    if not created:
        item.quantity = min(20, item.quantity + qty)
        item.save(update_fields=['quantity'])
    messages.success(request, f'«{product.name}» добавлен в корзину.')
    return redirect('cart')


@role_required('client')
@require_POST
def cart_update(request):
    for item in CartItem.objects.filter(user=request.user):
        raw = request.POST.get(f'qty_{item.pk}')
        if raw is None:
            continue
        try:
            qty = int(raw)
        except ValueError:
            continue
        if qty <= 0:
            item.delete()
        else:
            item.quantity = min(qty, 20)
            item.save(update_fields=['quantity'])
    messages.success(request, 'Корзина обновлена.')
    return redirect('cart')


@role_required('client')
@require_POST
def cart_remove(request, pk):
    CartItem.objects.filter(user=request.user, pk=pk).delete()
    messages.success(request, 'Позиция удалена из корзины.')
    return redirect('cart')


@role_required('client')
def my_orders(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items')
    return render(request, 'shop/my_orders.html', {'orders': orders})


@role_required('client')
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related('items'), pk=pk, user=request.user)
    return render(request, 'shop/order_detail.html', {'order': order})


@role_required('client')
def order_edit(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related('items'), pk=pk, user=request.user)
    if not order.can_client_edit():
        messages.error(request, 'Заказ уже обрабатывается и не может быть изменён.')
        return redirect('order_detail', pk=order.pk)
    form = OrderEditForm(request.POST or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
                remaining = 0
                for item in order.items.all():
                    try:
                        qty = int(request.POST.get(f'qty_{item.pk}', item.quantity))
                    except ValueError:
                        qty = item.quantity
                    if qty <= 0:
                        item.delete()
                    elif qty > 20:
                        raise ValueError('Количество не больше 20.')
                    else:
                        item.quantity = qty
                        item.save(update_fields=['quantity'])
                        remaining += 1
                if remaining == 0:
                    raise ValueError('В заказе должна остаться хотя бы одна позиция. Иначе удалите заказ.')
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, 'Заказ обновлён.')
            return redirect('order_detail', pk=order.pk)
    return render(request, 'shop/order_edit.html', {'order': order, 'form': form})


@role_required('client')
@require_POST
def order_delete(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if not order.can_client_edit():
        messages.error(request, 'Обработанный заказ удалить нельзя.')
        return redirect('order_detail', pk=order.pk)
    order.delete()
    messages.success(request, 'Заказ удалён.')
    return redirect('my_orders')


@role_required('manager')
def manager_orders(request):
    status = request.GET.get('status', '')
    orders = Order.objects.select_related('user').prefetch_related('items')
    if status in dict(Order.STATUS_CHOICES):
        orders = orders.filter(status=status)
    return render(
        request,
        'shop/manager_orders.html',
        {'orders': orders, 'status': status, 'statuses': Order.STATUS_CHOICES},
    )


@role_required('manager')
def manager_order(request, pk):
    order = get_object_or_404(Order.objects.select_related('user').prefetch_related('items'), pk=pk)
    if request.method == 'POST':
        status = request.POST.get('status', '')
        if status not in dict(Order.STATUS_CHOICES):
            messages.error(request, 'Некорректный статус.')
        else:
            order.status = status
            order.save(update_fields=['status'])
            messages.success(request, 'Статус заказа обновлён.')
            return redirect('manager_order', pk=order.pk)
    return render(request, 'shop/manager_order.html', {'order': order, 'statuses': Order.STATUS_CHOICES})


@role_required('admin')
def admin_dashboard(request):
    stats = {
        'categories': Category.objects.count(),
        'products': Product.objects.count(),
        'news': News.objects.count(),
        'clients': UserProfile.objects.filter(role__code='client').count(),
        'managers': UserProfile.objects.filter(role__code='manager').count(),
        'orders': Order.objects.count(),
    }
    return render(request, 'shop/admin/dashboard.html', {'stats': stats})


@role_required('admin')
def admin_categories(request):
    return render(request, 'shop/admin/categories.html', {'categories': Category.objects.all()})


@role_required('admin')
def admin_category_create(request):
    form = CategoryForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Категория добавлена.')
        return redirect('catalog')
    return render(request, 'shop/admin/category_form.html', {'form': form, 'title': 'Новая категория'})


@role_required('admin')
def admin_category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, request.FILES or None, instance=category)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Категория сохранена.')
        return redirect('admin_categories')
    return render(
        request,
        'shop/admin/category_form.html',
        {'form': form, 'title': 'Редактирование категории'},
    )


@role_required('admin')
@require_POST
def admin_category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    try:
        category.delete()
    except ProtectedError:
        messages.error(request, 'Сначала удалите товары этой категории.')
    else:
        messages.success(request, 'Категория удалена.')
    return redirect('admin_categories')


@role_required('admin')
def admin_products(request):
    products = Product.objects.select_related('category')
    return render(request, 'shop/admin/products.html', {'products': products})


@role_required('admin')
def admin_product_create(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        messages.success(request, f'Товар «{product.name}» добавлен.')
        return redirect('catalog')
    return render(request, 'shop/admin/product_form.html', {'form': form, 'title': 'Новый товар'})


@role_required('admin')
def admin_product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Товар сохранён.')
        return redirect('admin_products')
    return render(request, 'shop/admin/product_form.html', {'form': form, 'title': 'Редактирование товара'})


@role_required('admin')
@require_POST
def admin_product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    name = product.name
    product.delete()
    messages.success(request, f'Товар «{name}» удалён.')
    return redirect('admin_products')


@role_required('admin')
def admin_news(request):
    return render(request, 'shop/admin/news_list.html', {'news': News.objects.all()})


@role_required('admin')
def admin_news_create(request):
    form = NewsForm(request.POST or None, request.FILES or None, initial={'published_at': timezone.localdate()})
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Новость опубликована.')
        return redirect('admin_news')
    return render(request, 'shop/admin/news_form.html', {'form': form, 'title': 'Новая новость'})


@role_required('admin')
def admin_news_edit(request, pk):
    item = get_object_or_404(News, pk=pk)
    form = NewsForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Новость сохранена.')
        return redirect('admin_news')
    return render(request, 'shop/admin/news_form.html', {'form': form, 'title': 'Редактирование новости'})


@role_required('admin')
@require_POST
def admin_news_delete(request, pk):
    item = get_object_or_404(News, pk=pk)
    item.delete()
    messages.success(request, 'Новость удалена.')
    return redirect('admin_news')


@role_required('admin')
def admin_users(request):
    profiles = (
        UserProfile.objects.filter(role__code__in=['client', 'manager'])
        .select_related('user', 'role')
        .order_by('role__code', 'user__username')
    )
    return render(request, 'shop/admin/users.html', {'profiles': profiles})


@role_required('admin')
def admin_manager_create(request):
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        role = Role.objects.get(code='manager')
        UserProfile.objects.create(user=user, role=role, phone=form.cleaned_data['phone'])
        messages.success(request, f'Менеджер {user.username} зарегистрирован.')
        return redirect('admin_users')
    return render(request, 'shop/admin/manager_form.html', {'form': form})


@role_required('admin')
@require_POST
def admin_user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    profile = UserProfile.objects.filter(user=user).select_related('role').first()
    if user == request.user or profile is None or profile.role.code == 'admin':
        messages.error(request, 'Администратора удалить нельзя.')
        return redirect('admin_users')
    if profile.role.code not in {'client', 'manager'}:
        messages.error(request, 'Эту учётную запись удалить нельзя.')
        return redirect('admin_users')
    username = user.username
    user.delete()
    messages.success(request, f'Пользователь {username} удалён.')
    return redirect('admin_users')
