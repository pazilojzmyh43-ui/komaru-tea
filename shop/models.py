from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models


class Role(models.Model):
    code = models.CharField('Код', max_length=20, unique=True)
    name = models.CharField('Название', max_length=50)

    class Meta:
        verbose_name = 'Роль'
        verbose_name_plural = 'Роли'
        ordering = ['id']

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile', verbose_name='Пользователь'
    )
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='profiles', verbose_name='Роль')
    phone = models.CharField('Телефон', max_length=30, blank=True)
    address = models.CharField('Адрес', max_length=255, blank=True)

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    def __str__(self):
        return f'{self.user.username} ({self.role.name})'


class Category(models.Model):
    name = models.CharField('Название', max_length=120)
    description = models.TextField('Описание')
    image = models.ImageField('Изображение', upload_to='categories/', blank=True)
    position = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['position', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.position:
            last = Category.objects.aggregate(models.Max('position'))['position__max'] or 0
            self.position = last + 1
        super().save(*args, **kwargs)


class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='products', verbose_name='Категория'
    )
    name = models.CharField('Название', max_length=160)
    short_description = models.CharField('Краткое описание', max_length=300)
    full_description = models.TextField('Полное описание')
    price = models.DecimalField(
        'Цена, руб.', max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('1'))]
    )
    image = models.ImageField('Изображение', upload_to='products/')
    weight_grams = models.PositiveIntegerField('Масса, г', default=50)
    tea_type = models.CharField('Тип чая', max_length=80, blank=True)
    region = models.CharField('Регион', max_length=120, blank=True)
    position = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['position', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.position:
            last = Product.objects.filter(category=self.category).aggregate(models.Max('position'))['position__max'] or 0
            self.position = last + 1
        super().save(*args, **kwargs)


class News(models.Model):
    title = models.CharField('Заголовок', max_length=200)
    summary = models.CharField('Краткое содержание', max_length=400)
    text = models.TextField('Текст')
    published_at = models.DateField('Дата публикации')
    image = models.ImageField('Изображение', upload_to='news/', blank=True)

    class Meta:
        verbose_name = 'Новость'
        verbose_name_plural = 'Новости'
        ordering = ['-published_at', '-id']

    def __str__(self):
        return self.title


class Order(models.Model):
    STATUS_NEW = 'new'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_NEW, 'Новый'),
        (STATUS_PROCESSING, 'В обработке'),
        (STATUS_DONE, 'Выполнен'),
        (STATUS_CANCELLED, 'Отменён'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', verbose_name='Клиент')
    created_at = models.DateTimeField('Дата', auto_now_add=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    address = models.CharField('Адрес доставки', max_length=255)
    phone = models.CharField('Телефон', max_length=30)
    comment = models.TextField('Комментарий', blank=True)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ №{self.pk}'

    @property
    def total(self):
        return sum((item.line_total for item in self.items.all()), Decimal('0'))

    def can_client_edit(self):
        return self.status == self.STATUS_NEW


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name='Заказ')
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items', verbose_name='Товар'
    )
    product_name = models.CharField('Название', max_length=160)
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField('Количество', validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def __str__(self):
        return f'{self.product_name} × {self.quantity}'

    @property
    def line_total(self):
        return self.price * self.quantity


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items', verbose_name='Клиент')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items', verbose_name='Товар')
    quantity = models.PositiveIntegerField('Количество', default=1, validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = 'Позиция корзины'
        verbose_name_plural = 'Корзина'
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], name='unique_cart_product'),
        ]

    def __str__(self):
        return f'{self.user.username}: {self.product.name}'

    @property
    def line_total(self):
        return self.product.price * self.quantity
