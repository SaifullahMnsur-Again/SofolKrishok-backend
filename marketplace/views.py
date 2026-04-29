from rest_framework import viewsets, permissions
from rest_framework import status
from rest_framework.response import Response
from django.db import transaction
from django.db.models import F
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from .models import Product, Order, OrderItem, OrderStatusHistory
from .serializers import ProductSerializer, OrderSerializer


@method_decorator(name='list', decorator=swagger_auto_schema(
    tags=['Marketplace - Products'],
    operation_description='List products with optional category filtering.'
))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(
    tags=['Marketplace - Products'],
    operation_description='Get product details by ID.'
))
@method_decorator(name='create', decorator=swagger_auto_schema(
    tags=['Marketplace - Products'],
    operation_description='Create a new product listing (staff only).'
))
@method_decorator(name='update', decorator=swagger_auto_schema(
    tags=['Marketplace - Products'],
    operation_description='Replace an existing product (staff only).'
))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(
    tags=['Marketplace - Products'],
    operation_description='Partially update product fields (staff only).'
))
@method_decorator(name='destroy', decorator=swagger_auto_schema(
    tags=['Marketplace - Products'],
    operation_description='Soft-delete a product (staff only).'
))
class ProductViewSet(viewsets.ModelViewSet):
    """Marketplace product catalog management.

    Audience: Both

    Handles product browsing for all authenticated users and product management for staff roles.

    **Available Actions:**
    - GET /marketplace/products/ - List products
    - GET /marketplace/products/{id}/ - Retrieve product
    - POST /marketplace/products/ - Create product (staff)
    - PUT /marketplace/products/{id}/ - Replace product (staff)
    - PATCH /marketplace/products/{id}/ - Update product (staff)
    - DELETE /marketplace/products/{id}/ - Soft delete product (staff)

    **Filtering:**
    - category: Filter by product category

    **Permissions:**
    - list/retrieve: Any authenticated user
    - create/update/delete: sales, leads, managers, site_engineer
    """
    serializer_class = ProductSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Product.objects.exclude(status='deleted')
        staff_roles = {
            'sales', 'sales_team_member', 'sales_team_lead',
            'branch_manager', 'general_manager', 'site_engineer',
        }
        if user.role not in staff_roles:
            qs = qs.filter(status='active')
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        # Only sales, managers, and engineers can create/edit products
        return [permissions.IsAuthenticated()] # In a real app we'd use a custom permission class

    def check_permissions(self, request):
        super().check_permissions(request)
        if self.action not in ['list', 'retrieve']:
            if request.user.role not in [
                'sales', 'sales_team_member', 'sales_team_lead',
                'branch_manager', 'general_manager', 'site_engineer',
            ]:
                self.permission_denied(request, message="Only staff can manage products.")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@method_decorator(name='list', decorator=swagger_auto_schema(
    tags=['Marketplace - Orders'],
    operation_description='List orders visible to the current user role.'
))
@method_decorator(name='retrieve', decorator=swagger_auto_schema(
    tags=['Marketplace - Orders'],
    operation_description='Get detailed order information by ID.'
))
@method_decorator(name='create', decorator=swagger_auto_schema(
    tags=['Marketplace - Orders'],
    operation_description='Create a marketplace order with one or more order items.'
))
@method_decorator(name='update', decorator=swagger_auto_schema(
    tags=['Marketplace - Orders'],
    operation_description='Replace an order (typically staff workflow).'
))
@method_decorator(name='partial_update', decorator=swagger_auto_schema(
    tags=['Marketplace - Orders'],
    operation_description='Update order status or editable fields based on role rules.'
))
@method_decorator(name='destroy', decorator=swagger_auto_schema(
    tags=['Marketplace - Orders'],
    operation_description='Delete an order record if permitted.'
))
class OrderViewSet(viewsets.ModelViewSet):
    """Marketplace order lifecycle management.

    Audience: Both

    Supports order creation, stock reservation, status transitions, cancellation, and refund bookkeeping.

    **Available Actions:**
    - GET /marketplace/orders/ - List orders
    - GET /marketplace/orders/{id}/ - Retrieve order
    - POST /marketplace/orders/ - Place order
    - PATCH /marketplace/orders/{id}/ - Update order/status

    **Key Behaviors:**
    - Stock is decremented atomically at order placement
    - Customer cancellation restores stock
    - Completed debit transaction is marked refunded on cancellation
    - Refund credit transaction is created automatically

    **Role Rules:**
    - Customers: Can view own orders and cancel allowed statuses
    - Staff: Can view all orders and move fulfillment statuses
    """
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['sales', 'sales_team_member', 'sales_team_lead', 'general_manager', 'site_engineer']:
            return Order.objects.all()
        return Order.objects.filter(customer=user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_items = serializer.validated_data.pop('order_items', [])
        shipping_address = serializer.validated_data.get('shipping_address', '')
        notes = serializer.validated_data.get('notes', '')

        if not order_items:
            return Response({'error': 'No order items provided.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                order = Order.objects.create(
                    customer=request.user,
                    shipping_address=shipping_address,
                    notes=notes,
                    last_status_changed_by=request.user,
                )

                total_amount = 0
                for row in order_items:
                    product = Product.objects.select_for_update().filter(
                        id=row['product'],
                        status='active',
                    ).first()
                    if not product:
                        raise ValueError(f"Product {row['product']} is unavailable.")

                    quantity = int(row['quantity'])
                    if product.stock_quantity < quantity:
                        raise ValueError(
                            f"Insufficient stock for {product.name}. Available: {product.stock_quantity}."
                        )

                    unit_price = product.discount_price or product.price
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price_at_purchase=unit_price,
                    )

                    total_amount += unit_price * quantity
                    product.stock_quantity = F('stock_quantity') - quantity
                    product.save(update_fields=['stock_quantity'])

                order.total_amount = total_amount
                order.save(update_fields=['total_amount'])

                OrderStatusHistory.objects.create(
                    order=order,
                    previous_status=None,
                    new_status=Order.Status.PENDING,
                    changed_by=request.user,
                    note='Order placed by customer',
                )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        output = self.get_serializer(order)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        order = self.get_object()
        user = request.user
        requested_status = request.data.get('status')

        # Customers can only cancel their own pending/processing orders or update address/notes.
        if order.customer_id == user.id:
            if requested_status and requested_status != Order.Status.CANCELLED:
                return Response({'error': 'Customers can only cancel orders.'}, status=status.HTTP_403_FORBIDDEN)

            if requested_status == Order.Status.CANCELLED:
                if order.status in [Order.Status.SHIPPED, Order.Status.DELIVERED, Order.Status.RETURNED]:
                    return Response({'error': 'This order can no longer be cancelled.'}, status=status.HTTP_400_BAD_REQUEST)

                if order.status != Order.Status.CANCELLED:
                    with transaction.atomic():
                        previous_status = order.status
                        # Restore stock on cancellation.
                        for item in order.items.select_related('product').all():
                            item.product.stock_quantity = F('stock_quantity') + item.quantity
                            item.product.save(update_fields=['stock_quantity'])

                        order.status = Order.Status.CANCELLED
                        order.last_status_changed_by = user
                        order.save(update_fields=['status', 'last_status_changed_by'])

                        OrderStatusHistory.objects.create(
                            order=order,
                            previous_status=previous_status,
                            new_status=Order.Status.CANCELLED,
                            changed_by=user,
                            note='Cancelled by customer',
                        )

                        from finance.models import Transaction
                        debit_txn = Transaction.objects.filter(
                            order=order,
                            type='debit',
                            status='completed',
                        ).order_by('-created_at').first()
                        if debit_txn:
                            debit_txn.status = Transaction.Status.REFUNDED
                            debit_txn.metadata = {**debit_txn.metadata, 'refunded_by_order_cancel': True}
                            debit_txn.save(update_fields=['status', 'metadata'])

                            Transaction.objects.create(
                                user=order.customer,
                                type='credit',
                                status='completed',
                                amount=debit_txn.amount,
                                description=f"Refund for cancelled order #{order.id}",
                                reference_id=f"REF-{debit_txn.reference_id}",
                                order=order,
                                metadata={'source_transaction': debit_txn.id},
                            )

                serializer = self.get_serializer(order)
                return Response(serializer.data)

            # Update shipping details/notes for non-cancel requests.
            allowed_fields = {'shipping_address', 'notes'}
            for key in list(request.data.keys()):
                if key not in allowed_fields:
                    return Response({'error': f'Field {key} cannot be updated.'}, status=status.HTTP_400_BAD_REQUEST)

            serializer = self.get_serializer(order, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        # Staff can update operational status.
        if requested_status:
            if requested_status == order.status:
                serializer = self.get_serializer(order)
                return Response(serializer.data)

            previous_status = order.status
            serializer = self.get_serializer(order, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save(last_status_changed_by=user)

            OrderStatusHistory.objects.create(
                order=order,
                previous_status=previous_status,
                new_status=serializer.instance.status,
                changed_by=user,
                note='Moved on fulfillment board',
            )
            return Response(serializer.data)

        serializer = self.get_serializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
