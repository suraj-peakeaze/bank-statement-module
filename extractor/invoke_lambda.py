import boto3
import json
import os
import io
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from PyPDF2 import PdfReader
from .models import ExtractedDataUsingAzure_lambda
import logging

logger = logging.getLogger(__name__)


def AzureExtractorView(request):
    """
    Updated Django view for serverless architecture.
    Only handles UI, S3 upload, and workflow triggering.
    All processing is now done by Lambda functions.
    """
    if request.method == "POST":
        try:
            bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
            if not bucket_name:
                raise Exception("AWS_STORAGE_BUCKET_NAME environment variable not set")

            state_machine_arn = os.getenv("STATE_MACHINE_ARN")
            if not state_machine_arn:
                raise Exception("STATE_MACHINE_ARN environment variable not set")

            start_time = datetime.now()
            logger.info(f"Upload process started at {start_time}")

            # Extract user input
            user_email = request.POST.get("user_email", "")
            pdf_file = request.FILES.get("pdf_file")

            if not pdf_file:
                return render(
                    request,
                    "azure_extractor.html",
                    {"error": True, "message": "No PDF file provided"},
                )

            pdf_name = pdf_file.name.replace(".pdf", "")

            # Validate PDF
            pdf_file.seek(0)
            file_bytes = pdf_file.read()
            idx = file_bytes.find(b"%PDF-")

            if idx == -1:
                logger.error("Uploaded file is not a valid PDF - no PDF header found")
                return render(
                    request,
                    "azure_extractor.html",
                    {"error": True, "message": "Uploaded file is not a valid PDF"},
                )

            # Clean bytes and validate structure
            clean_bytes = file_bytes[idx:]
            try:
                reader = PdfReader(io.BytesIO(clean_bytes), strict=False)
                num_pages = len(reader.pages)
                logger.info(f"Valid PDF with {num_pages} pages")
            except Exception as e:
                logger.error(f"Invalid PDF file: {e}")
                return render(
                    request,
                    "azure_extractor.html",
                    {"error": True, "message": f"Invalid PDF file: {str(e)}"},
                )

            # Upload PDF to S3
            s3 = boto3.client("s3")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            s3_key = f"incoming_pdfs/{timestamp}_{pdf_name}.pdf"

            # Reset file pointer and upload
            pdf_file.seek(0)
            s3.upload_fileobj(pdf_file, bucket_name, s3_key)
            logger.info(f"PDF uploaded to s3://{bucket_name}/{s3_key}")

            # Create database record for job tracking
            job = ExtractedDataUsingAzure_lambda.objects.create(
                pdf_name=pdf_name,
                user_email=user_email if user_email else None,
                pdf_path=f"s3://{bucket_name}/{s3_key}",  # S3 path instead of local
                extracted_csv_path="",  # Will be updated by Lambda
                csv_name=f"{pdf_name}_final.csv",
                status="STARTED",
                num_pages=num_pages,
            )

            # Trigger Step Functions workflow
            sfn = boto3.client("stepfunctions")

            execution_input = {
                "job_id": str(job.id),
                "bucket": bucket_name,
                "pdf_key": s3_key,
                "pdf_name": pdf_name,
                "user_email": user_email,
                "num_pages": num_pages,
                "timestamp": timestamp,
            }
            print(execution_input)

            execution_name = f"ocr-job-{job.id}-{timestamp}"
            response = sfn.start_execution(
                stateMachineArn=state_machine_arn,
                name=execution_name,
                input=json.dumps(execution_input),
            )

            # Update job with execution details
            job.execution_arn = response["executionArn"]
            job.save()

            logger.info(f"Step Functions execution started: {response['executionArn']}")

            # Render success page
            return render(
                request,
                "processing_started.html",
                {
                    "job_id": job.id,
                    "email": user_email,
                    "pages": num_pages,
                    "pdf_name": pdf_name,
                    "execution_arn": response["executionArn"],
                },
            )

        except Exception as e:
            logger.error(f"Error in AzureExtractorView: {e}")
            return render(
                request,
                "azure_extractor.html",
                {"error": True, "message": f"Processing error: {str(e)}"},
            )

    # GET request - show upload form
    return render(request, "azure_extractor.html")


def job_status(request, job_id):
    """
    API endpoint to check processing job status.
    Used for real-time status updates from frontend.
    """
    try:
        job = ExtractedDataUsingAzure_lambda.objects.get(id=job_id)

        # Optional: Query Step Functions for real-time status
        if job.execution_arn:
            try:
                sfn = boto3.client("stepfunctions")
                execution = sfn.describe_execution(executionArn=job.execution_arn)
                step_function_status = execution.get("status", "UNKNOWN")

                # Map Step Functions status to our status
                if step_function_status == "SUCCEEDED":
                    job.status = "COMPLETED"
                elif step_function_status == "FAILED":
                    job.status = "FAILED"
                elif step_function_status == "RUNNING":
                    job.status = "PROCESSING"

                job.save()
            except Exception as e:
                logger.warning(f"Could not get Step Functions status: {e}")

        return JsonResponse(
            {
                "status": job.status,
                "progress": getattr(job, "progress", 0),
                "final_csv_url": getattr(job, "final_csv_url", None),
                "error_message": getattr(job, "error_message", None),
                "execution_arn": job.execution_arn,
            }
        )

    except ExtractedDataUsingAzure_lambda.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)


@csrf_exempt
def update_job_status(request):
    """
    Webhook endpoint for Lambda functions to update job status.
    Called by your aggregator Lambda when processing completes.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            job_id = data.get("job_id")

            if not job_id:
                return JsonResponse({"error": "job_id required"}, status=400)

            job = ExtractedDataUsingAzure_lambda.objects.get(id=job_id)

            # Update job fields
            if "status" in data:
                job.status = data["status"]
            if "progress" in data:
                job.progress = data["progress"]
            if "final_csv_url" in data:
                job.final_csv_url = data["final_csv_url"]
                job.extracted_csv_path = data[
                    "final_csv_url"
                ]  # For backward compatibility
            if "error_message" in data:
                job.error_message = data["error_message"]
            if "final_csv_key" in data:
                job.final_csv_s3_key = data["final_csv_key"]

            job.updated_at = datetime.now()
            job.save()

            logger.info(f"Job {job_id} status updated to {job.status}")
            return JsonResponse({"success": True})

        except ExtractedDataUsingAzure_lambda.DoesNotExist:
            return JsonResponse({"error": "Job not found"}, status=404)
        except Exception as e:
            logger.error(f"Error updating job status: {e}")
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "POST method required"}, status=405)


def download_result(request, job_id):
    """
    Generate download link for completed job results.
    Creates a presigned S3 URL for secure downloading.
    """
    try:
        job = ExtractedDataUsingAzure_lambda.objects.get(id=job_id)

        if job.status != "COMPLETED":
            return JsonResponse({"error": "Job not completed yet"}, status=400)

        if not hasattr(job, "final_csv_s3_key") or not job.final_csv_s3_key:
            return JsonResponse({"error": "No result file available"}, status=404)

        # Generate presigned URL for download
        s3 = boto3.client("s3")
        bucket_name = os.environ.get("PROCESSING_BUCKET")

        download_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": job.final_csv_s3_key},
            ExpiresIn=3600,  # 1 hour
        )

        return JsonResponse(
            {"download_url": download_url, "filename": f"{job.pdf_name}_final.csv"}
        )

    except ExtractedDataUsingAzure_lambda.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)
    except Exception as e:
        logger.error(f"Error generating download link: {e}")
        return JsonResponse({"error": str(e)}, status=500)
