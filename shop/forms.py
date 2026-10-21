from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Category, News, Order, Product


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(label='Имя', max_length=50)
    last_name = forms.CharField(label='Фамилия', max_length=50)
    email = forms.EmailField(label='Эл. почта')
    phone = forms.CharField(label='Телефон', max_length=30)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Логин'
        self.fields['password1'].label = 'Пароль'
        self.fields['password2'].label = 'Повтор пароля'
        for name in ('username', 'password1', 'password2'):
            self.fields[name].help_text = ''


class CheckoutForm(forms.Form):
    address = forms.CharField(label='Адрес доставки', max_length=255)
    phone = forms.CharField(label='Телефон', max_length=30)
    comment = forms.CharField(label='Комментарий к заказу', required=False, widget=forms.Textarea(attrs={'rows': 3}))


class OrderEditForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ('address', 'phone', 'comment')
        widgets = {'comment': forms.Textarea(attrs={'rows': 3})}


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'description', 'image')
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}

    def clean_image(self):
        return _clean_upload(self.cleaned_data.get('image'), required=False)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            'category',
            'name',
            'short_description',
            'full_description',
            'price',
            'weight_grams',
            'tea_type',
            'region',
            'image',
        )
        widgets = {
            'short_description': forms.Textarea(attrs={'rows': 3}),
            'full_description': forms.Textarea(attrs={'rows': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['image'].required = False

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image is False:
            raise forms.ValidationError('Изображение товара обязательно.')
        return _clean_upload(image, required=not self.instance.pk)


class NewsForm(forms.ModelForm):
    published_at = forms.DateField(
        label='Дата публикации',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        input_formats=['%Y-%m-%d'],
    )

    class Meta:
        model = News
        fields = ('title', 'summary', 'text', 'published_at', 'image')
        widgets = {
            'summary': forms.Textarea(attrs={'rows': 3}),
            'text': forms.Textarea(attrs={'rows': 8}),
        }

    def clean_image(self):
        return _clean_upload(self.cleaned_data.get('image'), required=False)


def _clean_upload(image, required):
    if not image:
        if required:
            raise forms.ValidationError('Загрузите изображение.')
        return image
    if getattr(image, 'size', 0) > 5 * 1024 * 1024:
        raise forms.ValidationError('Размер файла не должен превышать 5 МБ.')
    name = getattr(image, 'name', '')
    if name and '.' in name:
        ext = name.rsplit('.', 1)[-1].lower()
        if ext not in {'jpg', 'jpeg', 'png', 'webp', 'gif'}:
            raise forms.ValidationError('Допустимы файлы JPG, PNG, WEBP или GIF.')
    return image
