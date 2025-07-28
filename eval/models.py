from django.db import models
import uuid


# Create your models here.
class Evaluation(models.Model):
    id = models.UUIDField(("id"), primary_key=True, default=uuid.uuid4, editable=False)
    original_csv = models.FileField(upload_to="original_csvs")
    evaluation_score = models.FloatField()
    date_score = models.FloatField()
    credit_score = models.FloatField()
    debit_score = models.FloatField()
    description_score = models.FloatField()
    balance_score = models.FloatField()

    def __str__(self):
        return f"Evaluation {self.id}"
