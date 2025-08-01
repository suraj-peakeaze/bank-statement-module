from django.urls import path
from . import views, invoke_lambda


urlpatterns = [
    path("azure/", views.AzureExtractorView, name="azure_extractor"),
    path("", invoke_lambda.AzureExtractorView, name="invoke_lambda"),
    path("job_status/<int:job_id>/", invoke_lambda.job_status, name="job_status"),
    path(
        "update_job_status/", invoke_lambda.update_job_status, name="update_job_status"
    ),
    path(
        "download_result/<int:job_id>/",
        invoke_lambda.download_result,
        name="download_result",
    ),
]
