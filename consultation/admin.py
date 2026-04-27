from django.contrib import admin
from .models import ConsultationSlot, Ticket

@admin.register(ConsultationSlot)
class ConsultationSlotAdmin(admin.ModelAdmin):
    list_display = ('expert', 'date', 'start_time', 'end_time', 'shift', 'is_available')
    list_filter = ('is_available', 'shift', 'date')
    search_fields = ('expert__username',)

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'farmer', 'slot', 'status')
    list_filter = ('status',)
    search_fields = ('farmer__username', 'slot__expert__username', 'notes')
