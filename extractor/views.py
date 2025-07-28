import io
from PyPDF2 import PdfReader
from django.shortcuts import redirect, render
from pdf2image import convert_from_path
from .models import ExtractedDataUsingAzure
from .processing.azure.ocr_tool import AzureAgent
import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .processing.pre.handle_split_pdf import split_pdf_into_pages
from .processing.post.handle_csv import download_csv
import pandas as pd
from .utils.logger import (
    get_logger,
    setup_logging_for_each_page,
)
from datetime import datetime
import chardet
from .processing.gemini.cleaning.gemini_response import GeminiAgent
from .processing.gemini.extract_header import (
    extract_header_using_gemini,
)
from .processing.gemini.cleaning.clean_using_response import (
    process_gemini_response,
)
from .processing.post.handle_csv_to_xml import run_file_to_xml_converter
import re
from .utils.create_dir import create_dirs

from .processing.mail.mailer import EmailService

logger = get_logger(__name__)


# Create your views here.
def AzureExtractorView(request):
    if request.method == "POST":
        start_time = datetime.now()
        logger.info(f"Process Started at {start_time}")

        # Extract email from request
        user_email = request.POST.get("user_email", "")
        if user_email:
            logger.info(f"User email provided: {user_email}")
        else:
            logger.warning("No user email provided in request")

        pdf_file = request.FILES.get("pdf_file")
        pdf_name = pdf_file.name.strip(".pdf")

        # Read file bytes and validate PDF
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

        # Clean bytes by removing any junk before PDF header
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

        # Reset to use original file for further processing
        pdf_file.seek(0)
        logger.info(f"Processing file -> {pdf_name}")

        if pdf_file:
            (
                storage_dir,
                upload_dir,
                split_dir,
                image_dir,
                final_csv_dir,
                temp_csv_dir,
                xml_dir,
                extracted_data_dir,
            ) = create_dirs(pdf_file)
            pdf_path = os.path.join(upload_dir, pdf_name)
            path = default_storage.save(pdf_path, ContentFile(pdf_file.read()))
            full_pdf_path = default_storage.path(path)
            final_csv_path = f"{final_csv_dir}/{pdf_name}.csv"

            # Split PDF into pages
            parts = split_pdf_into_pages(full_pdf_path, output_dir=split_dir)

            # Process each part and collect image paths
            images = []
            i = 0
            csv_files = []
            column_map = []
            for part in parts:
                # Convert PDF part to images
                part_images = convert_from_path(part)
                i += 1
                for j, image in enumerate(part_images):
                    page_num = i

                    # Setup page-specific logger
                    page_logger = setup_logging_for_each_page(storage_dir, page_num)
                    page_logger.info(f"Starting processing for page {page_num}")

                    page_path = f"{image_dir}/page_{page_num}.png"

                    image.save(page_path, "PNG")
                    images.append(page_path)  # Add image path to images list

                    temp_path = f"{temp_csv_dir}/page_{page_num}.csv"
                    page_logger.info(f"Creating Azure agent for page {page_num}")

                    if not column_map:
                        # Extract headers using Gemini
                        header, is_valid_page = extract_header_using_gemini(
                            image=page_path, page_logger=page_logger
                        )

                        page_logger.info(f"header: {header}")
                        if is_valid_page:
                            # Dict mapping index to header
                            index_to_header = {
                                item["index"]: item["headers"] for item in header
                            }

                            # List of headers
                            headers_list = [item["headers"] for item in header]
                            column_map_with_index = index_to_header
                            column_map = headers_list
                        page_logger.info(f"column_map: {column_map}")

                        if not is_valid_page:
                            page_logger.info(
                                f"Page {page_num} is not a valid page, skipping."
                            )
                            break

                    # Extract data using Azure OCR
                    AzureAgent(
                        {images[page_num - 1]},
                        page_path,
                        page_num,
                        temp_path=temp_path,
                        page_logger=page_logger,
                    )

                    if not os.path.exists(temp_path):
                        page_logger.warning(
                            f"No CSV file found for page {page_num}, skipping."
                        )
                        continue

                    df = pd.read_csv(temp_path)
                    page_logger.info(f"[DEBUG] df: {df}")

                    page_logger.info("Converting to XML format")
                    # Convert CSV to XML format
                    xml_data = run_file_to_xml_converter(temp_path, xml_dir)
                    page_logger.info(f"xml_data:\n {str(xml_data)}")

                    # Call Gemini agent for data cleaning
                    page_logger.info("Calling Gemini agent for data cleaning")
                    gemini_agent = GeminiAgent()
                    json_response = gemini_agent.call_gemini(
                        image=page_path,
                        xml_output=xml_data,
                        headers=column_map_with_index,
                        page_logger=page_logger,
                    )

                    # Process Gemini response
                    extracted_data_path = f"{extracted_data_dir}/{page_num}.csv"
                    page_logger.info("Processing Gemini response")
                    try:
                        cleaned_data = process_gemini_response(
                            json_response,
                            temp_path,
                            extracted_data_path,
                            page_logger,
                        )
                    except Exception as e:
                        page_logger.error(f"Error in process_gemini_response: {e}")
                        continue
                    page_logger.info(f"Completed processing for page {page_num}")

            try:
                print(f"final_csv_dir: {final_csv_dir}")
                final_df = pd.DataFrame()  # Initialize as empty DataFrame

                csv_files = os.listdir(extracted_data_dir)
                if not csv_files:
                    logger.warning("No CSV files found in extracted_data directory")

                # Before processing files, order them by page number
                def extract_page_number(filename):
                    match = re.search(r"page_(\d+)\.csv$", filename)
                    if match:
                        return int(match.group(1))
                    return float("inf")  # Put files without a page number at the end

                # If you have a list of file paths, e.g., file_paths = [...]
                file_paths = sorted(csv_files, key=extract_page_number)

                for idx, file in enumerate(file_paths):
                    file_path = os.path.join(extracted_data_dir, file)
                    header = column_map
                    logger.info(f"header: {header}")
                    logger.info(f"final_df shape: {final_df.shape}")
                    logger.info(f"file:\n {file}")

                    reader = pd.read_csv(file_path)
                    if reader.columns.tolist() != header:
                        reader.columns = header
                        reader.to_csv(file_path, index=False)

                    # Check if first row is duplicate header
                    if reader.iloc[0].tolist() == header:
                        reader = reader.drop(reader.index[0])  # Drop first row
                        reader.to_csv(file_path, index=False)

                    with open(file_path, "rb") as f:
                        result = chardet.detect(f.read())
                        encoding = result["encoding"]

                    df = pd.read_csv(file_path, encoding=encoding)

                    final_df = pd.concat([final_df, df], ignore_index=True)

                final_df.to_csv(f"{final_csv_dir}/{pdf_name}.csv", index=False)

                # Save to database with email information
                try:
                    ExtractedDataUsingAzure.objects.create(
                        pdf_path=full_pdf_path,
                        extracted_csv_path=final_csv_path,
                        pdf_name=pdf_name,
                        csv_name=f"{pdf_name}.csv",
                        user_email=(
                            user_email if user_email else None
                        ),  # Store email if provided
                    )
                except Exception as e:
                    logger.error(f"Error creating ExtractedDataUsingAzure: {e}")
                    logger.error(f"pdf_path length: {len(full_pdf_path) if full_pdf_path else 0}")
                    logger.error(f"csv_path length: {len(final_csv_path) if final_csv_path else 0}")
                    logger.error(f"pdf_name length: {len(pdf_name) if pdf_name else 0}")
                    logger.error(f"user_email length: {len(user_email) if user_email else 0}")
                    raise

                # Send email notification if email was provided
                if user_email:
                    try:
                        logger.info(f"Sending email notification to: {user_email}")
                        email_service = EmailService()

                        # Calculate processing stats
                        end_time = datetime.now()
                        processing_duration = end_time - start_time
                        record_count = len(final_df) if not final_df.empty else 0

                        # Send email with CSV attachment
                        email_service.send_processing_complete_notification(
                            user_email=user_email,
                            pdf_name=pdf_file.name,
                            csv_path=final_csv_path,
                            processing_time=str(processing_duration).split(".")[
                                0
                            ],  # Remove microseconds
                            record_count=record_count,
                        )
                        logger.info("Email notification sent successfully")
                    except Exception as e:
                        logger.error(f"Failed to send email notification: {e}")
                        # Don't fail the entire process if email fails

            except Exception as e:
                logger.error(f"Error in final_df: {e}")
                return render(
                    request,
                    "azure_extractor.html",
                    {"error": True, "message": f"Error processing data: {str(e)}"},
                )

            response = download_csv(final_csv_path)
            response.status_code = 200
            end_time = datetime.now()
            logger.info(f"Process Ended at {end_time}")
            logger.info(f"Process took {end_time - start_time} for {len(parts)} pages")
            return response

    return render(request, "azure_extractor.html")
