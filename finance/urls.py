from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'plans', views.SubscriptionPlanViewSet, basename='plan')
router.register(r'ledger', views.TransactionViewSet, basename='transaction')

urlpatterns = [
    path('', include(router.urls)),
    path('subscription/', views.SubscriptionView.as_view(), name='subscription'),
    path('checkout/', views.CheckoutView.as_view(), name='checkout'),
    path('payment/callback/', views.PaymentCallbackView.as_view(), name='payment-callback'),
]
