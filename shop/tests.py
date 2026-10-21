from django.contrib.auth.models import User
from django.test import TestCase

from shop.models import Category, Product, Role, UserProfile


class ShopAccessTests(TestCase):
    def setUp(self):
        client_role = Role.objects.create(code='client', name='Клиент')
        manager_role = Role.objects.create(code='manager', name='Менеджер')
        admin_role = Role.objects.create(code='admin', name='Администратор')
        self.client_user = User.objects.create_user('client', password='ClientTea2026')
        self.manager_user = User.objects.create_user('manager', password='ManagerTea2026')
        self.admin_user = User.objects.create_user('admin', password='AdminTea2026', is_staff=True, is_superuser=True)
        UserProfile.objects.create(user=self.client_user, role=client_role)
        UserProfile.objects.create(user=self.manager_user, role=manager_role)
        UserProfile.objects.create(user=self.admin_user, role=admin_role)

    def test_home_is_public(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Komaru Tea')

    def test_guest_cart_redirects(self):
        response = self.client.get('/cart/')
        self.assertEqual(response.status_code, 302)

    def test_client_sees_cart_manager_does_not(self):
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.get('/cart/').status_code, 200)
        self.client.force_login(self.manager_user)
        self.assertEqual(self.client.get('/cart/').status_code, 302)
        self.assertEqual(self.client.get('/orders/manage/').status_code, 200)

    def test_admin_panel_closed_for_client(self):
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.get('/panel/').status_code, 302)
        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.get('/panel/').status_code, 200)

    def test_catalog_pages(self):
        category = Category.objects.create(name='Китайский чай', description='Описание')
        Product.objects.create(
            category=category,
            name='Лунцзин',
            short_description='Коротко',
            full_description='Полностью',
            price='100.00',
            image='products/longjing.jpg',
        )
        self.assertContains(self.client.get('/catalog/'), 'Китайский чай')
        self.assertContains(self.client.get(f'/catalog/category/{category.pk}/'), 'Лунцзин')
