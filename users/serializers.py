from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


def normalize_comma_tags(value: str) -> str:
    if not value:
        return ''
    parts = [part.strip() for part in str(value).split(',') if part.strip()]
    deduped = []
    seen = set()
    for part in parts:
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(key)
    return ', '.join(deduped)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'password', 'password_confirm', 'role', 'phone', 'address',
            'preferred_language',
        ]

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    def get_avatar_url(self, obj):
        request = self.context.get('request')
        if obj.avatar and hasattr(obj.avatar, 'url'):
            url = obj.avatar.url
            if request:
                return request.build_absolute_uri(url)
            return url
        return None

    def validate_expert_tags(self, value):
        return normalize_comma_tags(value)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'phone', 'address', 'avatar', 'avatar_url', 'preferred_language',
            'zone', 'expert_tags', 'is_active',
            'date_joined', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'username', 'role', 'date_joined', 'created_at', 'updated_at', 'avatar_url']


class UserListSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    def get_avatar_url(self, obj):
        request = self.context.get('request')
        if obj.avatar and hasattr(obj.avatar, 'url'):
            url = obj.avatar.url
            if request:
                return request.build_absolute_uri(url)
            return url
        return None

    def validate_expert_tags(self, value):
        return normalize_comma_tags(value)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'avatar', 'avatar_url', 'phone', 'zone', 'expert_tags', 'is_active', 'date_joined',
        ]

from .models import AuditLog, Notification

class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = AuditLog
        fields = ['id', 'username', 'action_type', 'description', 'timestamp']

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'notification_type', 'is_read', 'timestamp']
        read_only_fields = ['id', 'timestamp']
