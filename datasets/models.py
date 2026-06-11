from django.db import models
import uuid
from projects.models import Project
from accounts.models import User


class Dataset(models.Model):
    STATUS = [
        ("processing", "Processing"),
        ("ready", "Ready"),
        ("error", "Error"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    name = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=500)

    total_images = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS, default="processing")

    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)


class Image(models.Model):
    STATUS = [
        ("pending", "Pending"),
        ("assigned", "Assigned"),
        ("annotated", "Annotated"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)

    filename = models.CharField(max_length=500)
    storage_url = models.URLField()
    storage_public_id = models.CharField(max_length=500, null=True, blank=True)

    file_size_bytes = models.IntegerField()
    width_px = models.IntegerField()
    height_px = models.IntegerField()

    md5_hash = models.CharField(max_length=32)

    status = models.CharField(max_length=20, choices=STATUS, default="pending")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("dataset", "md5_hash")