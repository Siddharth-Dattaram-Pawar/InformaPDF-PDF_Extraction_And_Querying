from huggingface_hub import hf_hub_download, HfApi
from google.cloud import storage
import os
import io

# Hugging Face repo and folder details
repo_id = "gaia-benchmark/GAIA"
folders_to_check = ["2023/test", "2023/validation"]
bucket_name = "gaia_benchmark_dataset"

def upload_to_gcs(bucket_name, destination_blob_name, data):
    """Uploads a file-like object (data) to the GCS bucket."""
    storage_client = storage.Client()  # Uses the credentials from GOOGLE_APPLICATION_CREDENTIALS
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    
    # Upload directly from the in-memory buffer
    blob.upload_from_file(data)
    print(f"Uploaded to {bucket_name}/{destination_blob_name}")

def download_upload_pdf(repo_id, folders_to_check, bucket_name, token):
    api = HfApi()

    # Loop through both folders (test and validation)
    for folder_path in folders_to_check:
        # List all files in the folder on Hugging Face
        files = api.list_repo_files(repo_id=repo_id, repo_type="dataset", revision="main", token=token)
        # Filter for files in the specified folder and only PDFs
        pdf_files = [f for f in files if f.startswith(folder_path) and f.endswith(".pdf")]
        
        for file in pdf_files:
            try:
                # Download the PDF file from Hugging Face as a file-like object (Stream)
                file_url = hf_hub_download(repo_id=repo_id, filename=file, repo_type="dataset", token=token)
                
                # Open the downloaded file in binary read mode
                with open(file_url, "rb") as f:
                    file_data = io.BytesIO(f.read())  # Create an in-memory buffer with file data

                # Construct GCS path (same as file path from Hugging Face)
                gcs_path = file

                # Upload the in-memory buffer directly to GCS
                upload_to_gcs(bucket_name, gcs_path, file_data)
                print(f"Successfully uploaded: {gcs_path}")
            
            except Exception as e:
                print(f"Error downloading or uploading {file}: {str(e)}")

# Usage
token = "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"
download_upload_pdf(repo_id, folders_to_check, bucket_name, token)
