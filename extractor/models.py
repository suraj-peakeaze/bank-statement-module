from django.db import models
import uuid
from eval.models import Evaluation
from django.utils import timezone


# Create your models here.
class ExtractedDataUsingAzure(models.Model):
    id = models.UUIDField(("id"), primary_key=True, default=uuid.uuid4, editable=False)
    pdf_path = models.CharField(max_length=500)
    extracted_csv_path = models.CharField(max_length=500)
    evaluation = models.ForeignKey(
        Evaluation,
        on_delete=models.CASCADE,
        default=None,
        null=True,
        blank=True,
    )
    pdf_name = models.CharField(max_length=255, default=None, null=True, blank=True)
    csv_name = models.CharField(max_length=255, default=None, null=True, blank=True)
    user_email = models.EmailField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Email address of the user who uploaded the file",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When the processing was initiated"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="When the record was last updated"
    )

    def __str__(self):
        return f"{self.pdf_name} - {self.user_email or 'No Email'}"

    class Meta:
        ordering = ["-created_at"]


class ExtractedDataUsingAzure_lambda(models.Model):
    STATUS_CHOICES = [
        ("STARTED", "Started"),
        ("SPLITTING", "Splitting PDF"),
        ("PROCESSING", "Processing Pages"),
        ("AGGREGATING", "Aggregating Results"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    # Existing fields
    pdf_name = models.CharField(max_length=255)
    user_email = models.EmailField(null=True, blank=True)
    pdf_path = models.CharField(max_length=500)  # Now stores S3 path
    extracted_csv_path = models.CharField(max_length=500, blank=True)
    csv_name = models.CharField(max_length=255)

    # New fields for serverless
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="STARTED")
    progress = models.IntegerField(default=0)  # 0-100
    execution_arn = models.CharField(max_length=500, null=True, blank=True)
    final_csv_url = models.URLField(null=True, blank=True)
    final_csv_s3_key = models.CharField(max_length=500, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    num_pages = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.pdf_name} - {self.status}"
