from .models import CartItem, UserProfile


def shop_context(request):
    role = None
    cart_count = 0
    if request.user.is_authenticated:
        profile = UserProfile.objects.filter(user=request.user).select_related('role').first()
        if profile:
            role = profile.role.code
            if role == 'client':
                cart_count = CartItem.objects.filter(user=request.user).count()
    return {'user_role': role, 'cart_count': cart_count}
