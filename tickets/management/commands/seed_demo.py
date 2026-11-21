from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from tickets.models import Agent, AuditEvent, InternalNote, Message, Ticket

class Command(BaseCommand):
    help = 'Create the Frontdesk demo agents and tickets.'

    def handle(self, *args, **options):
        agents = {}
        for name, initials in [('Asha Menon', 'AM'), ('Rohan Shah', 'RS'), ('Meera Nair', 'MN'), ('Dev Kumar', 'DK')]:
            agents[name], _ = Agent.objects.get_or_create(name=name, defaults={'initials': initials})
        if Ticket.objects.exists():
            self.stdout.write(self.style.WARNING('Demo tickets already exist; nothing changed.'))
            return
        now = timezone.now()
        rows = [
            ('INC-0291', 'Checkout fails after card verification', 'Anita Joseph', 'anita.j@example.com', 'urgent', 'open', None, 5),
            ('INC-0304', 'Unable to export monthly report', 'Sanjay Rao', 'sanjay.r@example.com', 'medium', 'in_progress', agents['Asha Menon'], 28),
            ('INC-0318', 'Question about changing billing email', 'Nikhil Thomas', 'nikhil.t@example.com', 'small', 'waiting_customer', agents['Rohan Shah'], 40),
            ('INC-0322', 'Duplicate charge shown in dashboard', 'Priya Mathew', 'priya.m@example.com', 'urgent', 'resolved', agents['Meera Nair'], 62),
            ('INC-0327', 'Need invoice copy for March', 'George Kurian', 'george.k@example.com', 'small', 'open', None, 2),
        ]
        for number, subject, customer, email, priority, status, assignee, hours in rows:
            ticket = Ticket.objects.create(number=number, subject=subject, customer_name=customer, customer_email=email, priority=priority, status=status, assignee=assignee, created_at=now - timedelta(hours=hours))
            Message.objects.create(ticket=ticket, author_name=customer, body=f'{subject}. Please help me resolve this issue.', is_customer=True, created_at=ticket.created_at)
            if status in {'in_progress', 'waiting_customer', 'resolved'}:
                ticket.first_response_at = ticket.created_at + timedelta(hours=1)
                if status == 'waiting_customer': ticket.waiting_since = ticket.first_response_at
                if status == 'resolved': ticket.resolved_at = ticket.created_at + timedelta(hours=5); ticket.reopen_until = ticket.resolved_at + timedelta(days=7)
                ticket.save()
                Message.objects.create(ticket=ticket, author_name=assignee.name, body='I am checking this for you and will update you shortly.', is_customer=False, created_at=ticket.first_response_at)
            if number == 'INC-0304': InternalNote.objects.create(ticket=ticket, author_name='Asha Menon', body='Check worker logs for the large date range.', created_at=ticket.created_at + timedelta(hours=2))
            AuditEvent.objects.create(ticket=ticket, action='created', actor_name='System', detail='Ticket created from support intake', created_at=ticket.created_at)
        self.stdout.write(self.style.SUCCESS('Created Frontdesk demo data.'))
