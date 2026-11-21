import json
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import Agent, AuditEvent, InternalNote, Message, Ticket
from .services import can_reopen, serialize_ticket, sla_payload, working_minutes_between

@ensure_csrf_cookie
def dashboard(request):
    return render(request, 'index.html', {'agent_name': settings.FRONTDESK_AGENT_NAME})

def body_json(request):
    try:
        return json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return None

def actor(body):
    return (body or {}).get('actor') or settings.FRONTDESK_AGENT_NAME

def get_ticket(number):
    return Ticket.objects.select_related('assignee').prefetch_related('messages', 'internal_notes').get(number=number)

def auto_close_waiting():
    for ticket in Ticket.objects.filter(status=Ticket.Status.WAITING_CUSTOMER, waiting_since__isnull=False):
        if working_minutes_between(ticket.waiting_since, timezone.now()) >= 5 * 540:
            ticket.status, ticket.closed_at = Ticket.Status.CLOSED, timezone.now()
            ticket.save(update_fields=['status', 'closed_at', 'updated_at'])
            AuditEvent.objects.create(ticket=ticket, action='auto_closed', actor_name='System', detail='Closed after one working week without customer response')

@require_GET
def agents(request):
    return JsonResponse([{'id': a.id, 'name': a.name, 'initials': a.initials} for a in Agent.objects.filter(active=True)], safe=False)

@require_GET
def ticket_collection(request):
    auto_close_waiting()
    queryset = Ticket.objects.select_related('assignee').prefetch_related('messages', 'internal_notes')
    filter_name, query = request.GET.get('filter', 'all'), request.GET.get('q', '').strip().lower()
    if filter_name == 'late':
        queryset = [t for t in queryset if sla_payload(t)['is_late']]
    elif filter_name == 'waiting':
        queryset = queryset.filter(status=Ticket.Status.WAITING_CUSTOMER)
    elif filter_name == 'mine':
        queryset = queryset.filter(assignee__name=settings.FRONTDESK_AGENT_NAME)
    if query:
        queryset = [t for t in queryset if query in f'{t.number} {t.subject} {t.customer_name}'.lower()]
    return JsonResponse([serialize_ticket(t) for t in queryset], safe=False)

@require_GET
def ticket_detail(request, number):
    try:
        return JsonResponse(serialize_ticket(get_ticket(number)))
    except Ticket.DoesNotExist:
        return JsonResponse({'error': 'Ticket not found'}, status=404)

@require_POST
def claim_ticket(request, number):
    body, current_actor = body_json(request), actor(body)
    try:
        with transaction.atomic():
            ticket = Ticket.objects.select_for_update().select_related('assignee').get(number=number)
            if ticket.assignee_id:
                return JsonResponse({'error': f'Already assigned to {ticket.assignee.name}'}, status=409)
            agent, _ = Agent.objects.get_or_create(name=current_actor, defaults={'initials': ''.join(part[0] for part in current_actor.split()[:2]).upper()})
            ticket.assignee = agent
            if ticket.status == Ticket.Status.OPEN:
                ticket.status = Ticket.Status.IN_PROGRESS
            ticket.save(update_fields=['assignee', 'status', 'updated_at'])
            AuditEvent.objects.create(ticket=ticket, action='claimed', actor_name=current_actor, detail=f'Assigned to {agent.name}')
        return JsonResponse(serialize_ticket(get_ticket(number)))
    except Ticket.DoesNotExist:
        return JsonResponse({'error': 'Ticket not found'}, status=404)

@require_POST
def reply_ticket(request, number):
    body = body_json(request)
    text = (body or {}).get('body', '').strip()
    if not text:
        return JsonResponse({'error': 'Message cannot be empty'}, status=400)
    try:
        with transaction.atomic():
            ticket = Ticket.objects.select_for_update().get(number=number)
            Message.objects.create(ticket=ticket, author_name=actor(body), body=text, is_customer=False)
            if not ticket.first_response_at:
                ticket.first_response_at = timezone.now()
            if ticket.status == Ticket.Status.WAITING_CUSTOMER:
                ticket.status, ticket.waiting_since = Ticket.Status.IN_PROGRESS, None
            ticket.save(update_fields=['first_response_at', 'status', 'waiting_since', 'updated_at'])
            AuditEvent.objects.create(ticket=ticket, action='customer_reply_sent', actor_name=actor(body), detail='Public reply sent to customer')
        return JsonResponse(serialize_ticket(get_ticket(number)))
    except Ticket.DoesNotExist:
        return JsonResponse({'error': 'Ticket not found'}, status=404)

@require_POST
def note_ticket(request, number):
    body = body_json(request)
    text = (body or {}).get('body', '').strip()
    if not text:
        return JsonResponse({'error': 'Note cannot be empty'}, status=400)
    try:
        ticket = get_ticket(number)
        InternalNote.objects.create(ticket=ticket, author_name=actor(body), body=text)
        AuditEvent.objects.create(ticket=ticket, action='private_note_added', actor_name=actor(body), detail='Private team note added')
        return JsonResponse(serialize_ticket(get_ticket(number)))
    except Ticket.DoesNotExist:
        return JsonResponse({'error': 'Ticket not found'}, status=404)

@require_POST
def status_ticket(request, number):
    body = body_json(request)
    requested = (body or {}).get('status')
    if requested == 'reopen':
        requested = Ticket.Status.IN_PROGRESS
    if requested not in {choice for choice, _ in Ticket.Status.choices}:
        return JsonResponse({'error': 'Invalid status'}, status=400)
    try:
        with transaction.atomic():
            ticket = Ticket.objects.select_for_update().get(number=number)
            previous = ticket.status
            if previous == Ticket.Status.RESOLVED and requested == Ticket.Status.IN_PROGRESS and not can_reopen(ticket):
                return JsonResponse({'error': 'Outside the one-week reopen window. Create a new ticket instead.'}, status=409)
            ticket.status = requested
            if requested == Ticket.Status.WAITING_CUSTOMER:
                ticket.waiting_since = timezone.now()
            elif previous == Ticket.Status.WAITING_CUSTOMER:
                ticket.waiting_since = None
            if requested == Ticket.Status.RESOLVED:
                ticket.resolved_at, ticket.reopen_until = timezone.now(), timezone.now() + timedelta(days=7)
            if requested == Ticket.Status.CLOSED:
                ticket.closed_at = timezone.now()
            if requested == Ticket.Status.IN_PROGRESS and previous == Ticket.Status.RESOLVED:
                ticket.resolved_at = None
            ticket.save()
            AuditEvent.objects.create(ticket=ticket, action='status_changed', actor_name=actor(body), detail=f'{previous} -> {requested}')
        return JsonResponse(serialize_ticket(get_ticket(number)))
    except Ticket.DoesNotExist:
        return JsonResponse({'error': 'Ticket not found'}, status=404)

@require_GET
def ticket_audit(request, number):
    try:
        ticket = Ticket.objects.get(number=number)
        return JsonResponse([{'id': e.id, 'action': e.action, 'actor': e.actor_name, 'detail': e.detail, 'at': e.created_at.isoformat()} for e in ticket.audit_events.all()], safe=False)
    except Ticket.DoesNotExist:
        return JsonResponse({'error': 'Ticket not found'}, status=404)

@require_GET
def customer_view(request, number):
    try:
        return JsonResponse(serialize_ticket(get_ticket(number), include_notes=False))
    except Ticket.DoesNotExist:
        return JsonResponse({'error': 'Ticket not found'}, status=404)
