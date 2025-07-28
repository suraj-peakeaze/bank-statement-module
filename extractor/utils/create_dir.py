import os
from datetime import datetime


def create_dirs(pdf_name):
    storage_dir = f"media/azure/{datetime.now().strftime('%d-%m-%Y')}/v2/flash/{pdf_name}"
    os.makedirs(storage_dir, exist_ok=True)

    image_dir = f"{storage_dir}/image_split"
    os.makedirs(image_dir, exist_ok=True)

    upload_dir = f"{storage_dir}/uploaded_pdf"
    os.makedirs(upload_dir, exist_ok=True)

    split_dir = f"{storage_dir}/split_pdf"
    os.makedirs(split_dir, exist_ok=True)

    extracted_data_dir = f"{storage_dir}/extracted_csv"
    os.makedirs(extracted_data_dir, exist_ok=True)

    xml_dir = f"{storage_dir}/extracted_xml"
    os.makedirs(xml_dir, exist_ok=True)

    temp_csv_dir = f"{storage_dir}/temp_csv"
    os.makedirs(temp_csv_dir, exist_ok=True)

    final_csv_dir = f"{storage_dir}/final_csv"
    os.makedirs(final_csv_dir, exist_ok=True)
    return (
        storage_dir,
        upload_dir,
        split_dir,
        image_dir,
        final_csv_dir,
        temp_csv_dir,
        xml_dir,
        extracted_data_dir,
    )
