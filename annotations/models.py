from django.db import models
import uuid
from datasets.models import Image
from accounts.models import User


class AnnotationTask(models.Model):
    STATUS = [
        ("unassigned", "Unassigned"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    image = models.OneToOneField(Image, on_delete=models.CASCADE)
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS, default="unassigned")
    batch = models.CharField(max_length=30, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Annotation(models.Model):
    STATUS = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    task = models.ForeignKey(AnnotationTask, on_delete=models.CASCADE)
    annotated_by = models.ForeignKey(User, on_delete=models.CASCADE)

    labels = models.JSONField()
    notes = models.TextField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS, default="draft")

    version = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)


class Review(models.Model):
    DECISION = [
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    annotation = models.OneToOneField(Annotation, on_delete=models.CASCADE)
    reviewed_by = models.ForeignKey(User, on_delete=models.CASCADE)

    decision = models.CharField(max_length=10, choices=DECISION)
    comment = models.TextField(null=True, blank=True)

    reviewed_at = models.DateTimeField(auto_now_add=True)