from rest_framework import serializers
from .models import Product, Order, OrderItem, OrderStatusHistory


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    subtotal = serializers.ReadOnlyField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'quantity', 'price_at_purchase', 'subtotal']


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source='changed_by.username', read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = ['id', 'previous_status', 'new_status', 'changed_by', 'changed_by_name', 'note', 'changed_at']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    last_status_changed_by_name = serializers.CharField(source='last_status_changed_by.username', read_only=True)
    order_items = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="[{product: <id>, quantity: <int>}]",
    )

    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ['id', 'customer', 'total_amount', 'created_at', 'updated_at']

    def validate_order_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one order item is required.")

        normalized = []
        for raw in value:
            product_id = raw.get('product')
            quantity = int(raw.get('quantity', 0))
            if not product_id or quantity <= 0:
                raise serializers.ValidationError("Each item must include valid product and quantity.")
            normalized.append({'product': int(product_id), 'quantity': quantity})
        return normalized
