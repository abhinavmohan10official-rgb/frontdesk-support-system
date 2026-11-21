from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/agents', views.agents, name='agents'),
    path('api/tickets', views.ticket_collection, name='ticket_collection'),
    path('api/tickets/<str:number>', views.ticket_detail, name='ticket_detail'),
    path('api/tickets/<str:number>/claim', views.claim_ticket, name='claim_ticket'),
    path('api/tickets/<str:number>/reply', views.reply_ticket, name='reply_ticket'),
    path('api/tickets/<str:number>/note', views.note_ticket, name='note_ticket'),
    path('api/tickets/<str:number>/status', views.status_ticket, name='status_ticket'),
    path('api/tickets/<str:number>/audit', views.ticket_audit, name='ticket_audit'),
    path('api/tickets/<str:number>/customer-view', views.customer_view, name='customer_view'),
]
