from django.db import models
import uuid
from accounts.models import User


class Project(models.Model):
    STATUS = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("in_review", "In Review"),
        ("completed", "Completed"),
        ("archived", "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="draft")

    label_set = models.JSONField()

    deadline = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)


class ProjectMember(models.Model):
    ROLE = [
        ("annotator", "Annotator"),
        ("reviewer", "Reviewer"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    role_in_project = models.CharField(max_length=20, choices=ROLE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("project", "user")