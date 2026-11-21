from django.contrib import admin
from .models import Agent, AuditEvent, InternalNote, Message, Ticket

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('number', 'subject', 'priority', 'status', 'assignee', 'created_at')
    list_filter = ('priority', 'status')
    search_fields = ('number', 'subject', 'customer_name', 'customer_email')

admin.site.register(Agent)
admin.site.register(Message)
admin.site.register(InternalNote)

@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'action', 'actor_name', 'detail', 'created_at')
    readonly_fields = ('ticket', 'action', 'actor_name', 'detail', 'created_at')
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
