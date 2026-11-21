from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.conf import settings
from django.utils import timezone

IST = ZoneInfo('Asia/Kolkata')
WORK_START, WORK_END = time(9, 30), time(18, 30)
POLICY = {'urgent': {'response_minutes': 120, 'resolution_days': 1}, 'medium': {'response_minutes': 270, 'resolution_days': 3}, 'small': {'response_minutes': 540, 'resolution_days': 5}}

def is_working_day(day): return day.weekday() < 5 and day.isoformat() not in settings.FESTIVAL_HOLIDAYS

def clamp_to_working_start(value):
    value = value.astimezone(IST)
    if not is_working_day(value.date()) or value.time() >= WORK_END:
        day = value.date() + timedelta(days=1)
        while not is_working_day(day): day += timedelta(days=1)
        return datetime.combine(day, WORK_START, IST)
    if value.time() < WORK_START: return datetime.combine(value.date(), WORK_START, IST)
    return value

def add_working_minutes(start, minutes):
    cursor, remaining = clamp_to_working_start(start), float(minutes)
    while remaining > 0:
        end = datetime.combine(cursor.date(), WORK_END, IST)
        available = max(0, (end - cursor).total_seconds() / 60)
        used = min(remaining, available)
        cursor += timedelta(minutes=used); remaining -= used
        if remaining > 0: cursor = clamp_to_working_start(cursor + timedelta(minutes=1))
    return cursor

def working_minutes_between(start, end):
    if end <= start: return 0
    cursor, finish, total = clamp_to_working_start(start), end.astimezone(IST), 0
    while cursor < finish:
        day_end = datetime.combine(cursor.date(), WORK_END, IST)
        total += max(0, (min(day_end, finish) - cursor).total_seconds() / 60)
        cursor = clamp_to_working_start(day_end + timedelta(minutes=1))
    return total

def due_times(ticket):
    policy = POLICY[ticket.priority]
    response_due = ticket.first_response_at or add_working_minutes(ticket.created_at, policy['response_minutes'])
    created = timezone.localtime(ticket.created_at, IST)
    if ticket.priority == 'urgent':
        same_day_end = datetime.combine(created.date(), WORK_END, IST)
        resolution_due = same_day_end if is_working_day(created.date()) and created.time() < WORK_END else add_working_minutes(ticket.created_at, 540)
    else:
        resolution_due = add_working_minutes(ticket.created_at, policy['resolution_days'] * 540)
    return response_due, resolution_due

def sla_payload(ticket):
    response_due, resolution_due = due_times(ticket)
    now, resolved = timezone.now(), ticket.status in {ticket.Status.RESOLVED, ticket.Status.CLOSED}
    response_late, resolution_late = not ticket.first_response_at and now > response_due, not resolved and now > resolution_due
    return {'first_due_at': response_due.isoformat(), 'resolution_due_at': resolution_due.isoformat(), 'response_late': response_late, 'resolution_late': resolution_late, 'is_late': response_late or resolution_late}

def can_reopen(ticket): return ticket.status == ticket.Status.RESOLVED and ticket.reopen_until and timezone.now() <= ticket.reopen_until

def serialize_ticket(ticket, include_notes=True):
    data = {'id': ticket.number, 'subject': ticket.subject, 'customer': ticket.customer_name, 'email': ticket.customer_email, 'priority': ticket.priority, 'status': ticket.status, 'assignee': {'id': ticket.assignee_id, 'name': ticket.assignee.name, 'initials': ticket.assignee.initials} if ticket.assignee else None, 'created_at': ticket.created_at.isoformat(), 'first_response_at': ticket.first_response_at.isoformat() if ticket.first_response_at else None, 'resolved_at': ticket.resolved_at.isoformat() if ticket.resolved_at else None, 'messages': [{'id': message.id, 'author': message.author_name, 'body': message.body, 'kind': 'customer' if message.is_customer else 'agent', 'created_at': message.created_at.isoformat()} for message in ticket.messages.all()], **sla_payload(ticket)}
    if include_notes: data['notes'] = [{'id': note.id, 'author': note.author_name, 'body': note.body, 'created_at': note.created_at.isoformat()} for note in ticket.internal_notes.all()]
    return data
