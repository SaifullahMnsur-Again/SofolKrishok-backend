from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone')
    ordering = ('username',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Platform Info', {'fields': ('role', 'phone', 'address', 'avatar', 'preferred_language')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Platform Info', {'fields': ('role', 'phone', 'preferred_language')}),
    )
