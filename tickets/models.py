from django.db import models
from django.utils import timezone

class Agent(models.Model):
    name = models.CharField(max_length=120, unique=True)
    initials = models.CharField(max_length=4)
    active = models.BooleanField(default=True)
    def __str__(self): return self.name

class Ticket(models.Model):
    class Priority(models.TextChoices):
        URGENT = 'urgent', 'Urgent'
        MEDIUM = 'medium', 'Medium'
        SMALL = 'small', 'Small'
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_PROGRESS = 'in_progress', 'In progress'
        WAITING_CUSTOMER = 'waiting_customer', 'Waiting on customer'
        RESOLVED = 'resolved', 'Resolved'
        CLOSED = 'closed', 'Closed'
    number = models.CharField(max_length=32, unique=True)
    subject = models.CharField(max_length=240)
    customer_name = models.CharField(max_length=120)
    customer_email = models.EmailField()
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)
    assignee = models.ForeignKey(Agent, null=True, blank=True, on_delete=models.PROTECT, related_name='tickets')
    created_at = models.DateTimeField(default=timezone.now)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    waiting_since = models.DateTimeField(null=True, blank=True)
    reopen_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['status', 'priority']), models.Index(fields=['assignee', 'status'])]
    def __str__(self): return f'{self.number} - {self.subject}'

class Message(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    author_name = models.CharField(max_length=120)
    body = models.TextField()
    is_customer = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    class Meta: ordering = ['created_at']

class InternalNote(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='internal_notes')
    author_name = models.CharField(max_length=120)
    body = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    class Meta: ordering = ['created_at']

class AuditEvent(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name='audit_events')
    action = models.CharField(max_length=80)
    actor_name = models.CharField(max_length=120)
    detail = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    class Meta: ordering = ['created_at']
    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('Audit events are immutable')
        return super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        raise ValueError('Audit events are immutable')
