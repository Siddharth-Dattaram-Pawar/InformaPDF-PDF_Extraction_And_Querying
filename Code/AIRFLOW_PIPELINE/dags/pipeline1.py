from huggingface_hub import hf_hub_download, HfApi
from google.cloud import storage
import os
import io
import PyPDF2
import requests  # For calling PDF.co API
from airflow import DAG
from airflow.operators.python import PythonOperator
import pendulum
from dotenv import load_dotenv
import logging
from datetime import timedelta
from typing import List, Optional

# Load environment variables
load_dotenv()
gcp_creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
hf_token = os.getenv('HUGGINGFACE_TOKEN')
pdf_co_api_key = os.getenv('PDFCO_API_KEY')

# Hugging Face repo and folder details
repo_id = "gaia-benchmark/GAIA"
folders_to_check = ["2023/test", "2023/validation"]
bucket_name = "gaia_benchmark_dataset"

# Define the default arguments
default_args = {
    'owner': 'airflow',
    'start_date': pendulum.today('UTC').add(days=-1),
    'retries': 1,
}

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the DAG using the with context manager
with DAG(
    'download_upload_pdf_pipeline',
    default_args=default_args,
    description='A pipeline to check, download, upload PDFs and extract contents',
    schedule='@daily',
) as dag:

    def pdf_exists_in_gcs(bucket_name: str, file_name: str) -> bool:
        """Check if the PDF file exists in GCS."""
        
        try:
            storage_client = storage.Client.from_service_account_json(gcp_creds_path)
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(file_name)
            exists = blob.exists()
            logger.info(f"Checked GCS for {file_name}: Exists = {exists}")
            return exists
        
        except Exception as e:
            logger.error(f"Error checking existence of {file_name} in GCS: {e}")
            return False 

    def text_exists_in_gcs(bucket_name: str, text_file_name: str) -> bool:
        """Check if the extracted text file exists in GCS."""
        
        try:
            storage_client = storage.Client.from_service_account_json(gcp_creds_path)
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(text_file_name) 
            exists = blob.exists()
            logger.info(f"Checked GCS for {text_file_name}: Exists = {exists}")
            return exists
        
        except Exception as e:
            logger.error(f"Error checking existence of {text_file_name} in GCS: {e}")
            return False  

    def download_pdf(file: str) -> str:
        """Download PDF from Hugging Face if it doesn't exist in GCS."""
        
        try:
            logger.info(f"Downloading PDF: {file}")
            file_path = hf_hub_download(repo_id=repo_id, filename=file, repo_type="dataset", token=hf_token)
            logger.info(f"Successfully downloaded PDF: {file} to {file_path}")
            return file_path
       
        except Exception as e:
            logger.error(f"Error downloading PDF {file}: {e}")
            raise 

    def upload_to_gcs(bucket_name: str, file_path: str, file_name: str) -> None:
        """Uploads a file-like object to the GCS bucket."""
        
        try:
            storage_client = storage.Client.from_service_account_json(gcp_creds_path)
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(file_name)
            with open(file_path, "rb") as f:
                blob.upload_from_file(f)
            logger.info(f"Uploaded to {bucket_name}/{file_name}")
        
        except Exception as e:
            logger.error(f"Error uploading {file_name} to GCS: {e}")
            raise  

    def extract_and_upload_contents(pdf_file_path: str, pdf_file_name: str) -> None:
        """Extract contents from the PDF using PyPDF2 and upload to GCS."""
        
        extracted_text = ""
        gcs_text_path = f"pdf_extract/{os.path.splitext(pdf_file_name)[0]}.txt"

        # Check if the text file already exists before extracting
        if text_exists_in_gcs(bucket_name, gcs_text_path):
            logger.info(f"Extracted text for {pdf_file_name} already exists. Skipping extraction.")
            return  # Skip extraction if the text file already exists

        logger.info(f"Starting to extract contents from {pdf_file_name} at {pdf_file_path}")

        try:
            with open(pdf_file_path, "rb") as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                logger.info(f"PDF file {pdf_file_name} has {len(pdf_reader.pages)} pages.")

                for page_number, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text() or ""
                    extracted_text += page_text + "\n"
                    logger.debug(f"Extracted text from page {page_number + 1}: {page_text[:100]}...")  # Log the first 100 chars

            # Check if any text was extracted
            if not extracted_text.strip():
                logger.warning(f"No text was extracted from {pdf_file_name}.")
            else:
                logger.info(f"Successfully extracted text from {pdf_file_name}. Uploading to GCS...")

            # Upload extracted text
            text_blob = storage_client.bucket(bucket_name).blob(gcs_text_path)
            text_blob.upload_from_string(extracted_text)
            logger.info(f"Uploaded extracted text to {bucket_name}/{gcs_text_path}")

        except Exception as e:
            logger.error(f"Error extracting contents from {pdf_file_name}: {e}")
    
    def generate_signed_url(bucket_name: str, blob_name: str) -> str:
        """Generate a signed URL for the PDF file in GCS."""
        
        storage_client = storage.Client.from_service_account_json(gcp_creds_path)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Generate a signed URL valid for 1 hour
        url = blob.generate_signed_url(expiration=timedelta(hours=1))
        logger.info(f"Generated signed URL for {blob_name}: {url}")
        return url

    def extract_using_pdfco(pdf_file_path: str, pdf_file_name: str) -> None:
        """Extract contents from the PDF using PDF.co API and upload to GCS."""
        
        extracted_text = ""
        gcs_text_path = f"pdfextract_pdfco/{os.path.splitext(pdf_file_name)[0]}.txt"

        # Check if the text file already exists before extracting
        if text_exists_in_gcs(bucket_name, gcs_text_path):
            logger.info(f"Extracted text for {pdf_file_name} using PDF.co already exists. Skipping extraction.")
            return  
        
        signed_url = generate_signed_url(bucket_name, pdf_file_name)
        logger.info(f"Extracting contents from {pdf_file_name} using PDF.co API...")
        
        try:
            response = requests.post(
                "https://api.pdf.co/v1/pdf/convert/to/text",
                headers={"x-api-key": pdf_co_api_key},
                json={
                    "url": signed_url,
                    "inline": True
                }
            )

            if response.status_code == 200:
                extracted_text = response.json().get("body", "")
                if extracted_text:
                    # Upload extracted text
                    storage_client = storage.Client.from_service_account_json(gcp_creds_path)
                    text_blob = storage_client.bucket(bucket_name).blob(gcs_text_path)
                    text_blob.upload_from_string(extracted_text)
                    logger.info(f"Uploaded extracted text to {bucket_name}/{gcs_text_path}")
                else:
                    logger.warning(f"No text was extracted using PDF.co for {pdf_file_name}.")
            else:
                logger.error(f"Error extracting text using PDF.co for {pdf_file_name}: {response.text}")

        except Exception as e:
            logger.error(f"Error extracting contents from {pdf_file_name} using PDF.co: {e}")

    def process_pdfs(**kwargs) -> None:
        """Main logic to process PDFs."""
        
        api = HfApi()
        for folder_path in folders_to_check:
            try:
                files = api.list_repo_files(repo_id=repo_id, repo_type="dataset", revision="main", token=hf_token)
                pdf_files = [f for f in files if f.startswith(folder_path) and f.endswith(".pdf")]
                for pdf_file in pdf_files:
                    # Check if PDF exists in GCS
                    pdf_exists = pdf_exists_in_gcs(bucket_name, pdf_file)
                    gcs_text_path = f"pdf_extract/{os.path.splitext(pdf_file)[0]}.txt"
                    pdfco_text_path = f"pdfextract_pdfco/{os.path.splitext(pdf_file)[0]}.txt"
                    
                    #Cgeck if text extract exists
                    text_exists = text_exists_in_gcs(bucket_name, gcs_text_path)
                    pdfco_exists = text_exists_in_gcs(bucket_name, pdfco_text_path)

                    if pdf_exists and text_exists and pdfco_exists:
                        logger.info(f"{pdf_file} exists in GCS and extracted text from both methods already exists. Skipping extraction.")
                        continue  # Skip both PDF download and extraction

                    elif pdf_exists and text_exists and not pdfco_exists:
                        logger.info(f"{pdf_file} exists in GCS but extracted text using PDF.co does not. Proceeding to extract using PDF.co...")
                        extract_using_pdfco(pdf_file, pdf_file)
                        continue

                    elif pdf_exists and not text_exists and pdfco_exists:
                        logger.info(f"{pdf_file} exists in GCS but extracted text using PyPDF does not. Proceeding to extract using PyPDF...")
                        extract_and_upload_contents(pdf_file, pdf_file)
                        continue

                    else: 
                        logger.info(f"{pdf_file} does not exist in GCS. Downloading and processing...")
                        
                        # Download PDF since it does not exist in GCS
                        file_path = download_pdf(pdf_file)
                        
                        # Upload to GCS
                        upload_to_gcs(bucket_name, file_path, pdf_file)
                        
                        # Extract contents using PyPDF
                        extract_and_upload_contents(file_path, pdf_file)
                        
                        # Extract contents using PDF.co
                        extract_using_pdfco(file_path, pdf_file)

            except Exception as e:
                logger.error(f"Error processing PDFs in folder {folder_path}: {e}")

    # Define the task
    process_pdf_task = PythonOperator(
        task_id='process_pdf_task',
        python_callable=process_pdfs,
    )
