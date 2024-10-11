from diagrams import Diagram, Cluster, Edge
from diagrams.custom import Custom
from diagrams.gcp.storage import GCS  # Google Cloud Storage
from diagrams.gcp.database import SQL  # Google Cloud SQL
from diagrams.gcp.compute import GCE  # Google Cloud Compute Engine
from diagrams.onprem.client import User
from diagrams.onprem.container import Docker
from diagrams.onprem.workflow import Airflow

huggingface_icon = "hf.png"  # Path to the Hugging Face logo
pypdf_icon = "pypdf.png"
pdfco_icon = "pdfco.png"

# Load your custom Hugging Face icon
with Diagram("Updated System Architecture", show=True):

    # User interaction
    user = User("User")

    # Custom Hugging Face icon
    huggingface_icon = Custom("Hugging Face", huggingface_icon)


    # Frontend interactions
    with Cluster("Frontend"):
        with Cluster("Streamlit App"):
            registration = User("Registration Page")
            login = User("Login Page")
            qa_interface = User("Question Answering Interface")

    # Backend with FastAPI
    with Cluster("Backend"):
        with Cluster("FastAPI"):
            auth = User("Authentication (JWT)")
            endpoints = User("Protected Endpoints")
            business_logic = User("Business Logic")

    # Airflow for pipeline
    with Cluster("DAG"):
        airflow = Airflow("Airflow Pipeline")
        with Cluster("Text Extraction"):
            pypdf = Custom("Pypdf (Open-Source)", pypdf_icon)
            pdf_co = Custom("PDF.co (API/Enterprise)", pdfco_icon)

    # Google Cloud storage instead of S3
    gcs_storage = GCS("Google Cloud Storage")

    # Google Cloud SQL
    cloud_sql = SQL("Google Cloud SQL")

    # Deployment using Docker and Google Cloud
    with Cluster("Deployment"):
        docker = Docker("Docker Compose")
        gce = GCE("Google Cloud Compute Engine")

    # Interactions
    user >> Edge(label="Interact") >> registration
    registration >> Edge(label="API Calls") >> auth
    auth >> Edge(label="Database Queries") >> cloud_sql
    auth >> Edge(label="Text Extraction Requests") >> airflow
    airflow >> Edge(label="Extract Text") >> [pypdf, pdf_co]
    
    # Storing extracted text in Google Cloud Storage
    [pypdf, pdf_co] >> Edge(label="Store Extracted Text") >> gcs_storage
    huggingface_icon >> Edge(label="Use Hugging Face Model") >> airflow

    # Deployment
    docker >> Edge(label="Deploy") >> gce
    gce >> Edge(label="Host Applications") >> [registration, auth]

    # Additional interactions for clarity
    # login >> Edge(label="API Calls") >> auth
    # qa_interface >> Edge(label="API Calls") >> endpoints
    endpoints >> Edge(label="Database Queries") >> cloud_sql
    endpoints >> Edge(label="Text Extraction Requests") >> airflow
    huggingface_icon >> Edge(label="Store Processed Data") >> gcs_storage  # Store processed data in GCS