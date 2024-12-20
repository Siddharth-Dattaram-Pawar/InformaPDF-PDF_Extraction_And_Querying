# InformaPDF-PDF_Extraction_And_Querying

## Project Overview

The project, titled "InformaPDF", also features a client-facing application built using FastAPI and Streamlit, enabling users to securely browse and query PDFs. JWT authentication was integrated to ensure secure user access, while the OpenAI API was utilized for intelligent content querying and response generation. User data, including hashed credentials, was securely stored in a MySQL database hosted on Google Cloud Platform (GCP).

**Details :** Developed an Airflow pipeline to automate the fetching, extraction, and storage of PDFs from the GAIA Hugging Face Repository. Text extraction was implemented using PyPDF2 (open-source) and PDF.co (API/enterprise), with the extracted content stored in Google Cloud Storage (GCS) for efficient access and processing.Docker was employed for containerization, streamlining the deployment of the Airflow pipeline, FastAPI backend, and Streamlit frontend. The project successfully combines automation, text extraction, and user interaction to deliver a streamlined and secure solution for PDF text extraction and exploration.

[![Codelabs](https://img.shields.io/badge/Codelabs-green?style=for-the-badge)](https://codelabs-preview.appspot.com/?file_id=1PtPbQA_wmCll14lt--FDn1jZeQYlErJ-qFyUNH8iI1g#0)

**Youtube Video :** https://youtu.be/X00lL-V44V0

**Streamlit Deployment :** https://streamlit-service-61122194920.us-east1.run.app/

**FastAPI Deployment :** https://fastapi-service-61122194920.us-east1.run.app/

### Attestation

WE ATTEST THAT WE HAVEN'T USED ANY OTHER STUDENTS' WORK IN OUR ASSIGNMENT AND ABIDE BY THE POLICIES LISTED IN THE STUDENT HANDBOOK

## Contribution: 

| **Contributor**       | **Contribution Percentage** |
|------------------------|-----------------------------|
| **Vaishnavi Veerkumar** | 33%                        |
| **Sriram Venkatesh**    | 33%                        |
| **Siddharth Pawar**      | 33%                        |

## Table of Contents
![Project Architecture](Diagrams/system_architecture.png)
- [Technologies Used](#technologies-used)
- [Setup and Installation](#setup-and-installation)
- [Environment Setup](#environment-setup)
- [Running the Project](#running-the-project)
  - [Airflow Pipelines](#airflow-pipelines)
  - [FastAPI Application](#fastapi-application)
  - [Streamlit Application](#streamlit-application)
  - [Deployment](#deployment)

## Technologies Used

| **Technology/Tool**         | **Purpose**                                                                                         |
|-----------------------------|-----------------------------------------------------------------------------------------------------|
| **Apache Airflow**          | Automates the data acquisition process for PDF files.                                              |
| **Text Extraction Tools**   | Utilized PyPDF (open-source) and PDF.co (API/enterprise) for text extraction from PDFs.             |
| **FastAPI**                 | Implements user registration, login functionality, and JWT authentication.                         |
| **Streamlit**               | Develops a user-friendly interface for registration, login, and Question Answering.                |
| **Google Cloud Storage (GCS)** | Stores PDFs fetched from Hugging Face and extracted text for efficient access and processing.    |
| **Google Cloud SQL**        | Stores user data, including hashed login credentials, ensuring scalability and secure data management. |
| **Docker Compose**          | Containerizes and deploys applications to a public cloud platform.                                 |
| **GitHub**                  | Facilitates version control and collaboration.                                                     |
| **OpenAI API**              | Enables intelligent querying and response generation based on user queries related to extracted content. |


## Setup and Installation

### **GCP Setup**:
    
    *   Make sure your GCP credentials are set correctly to access the GCS bucket containing the task files as well as the SQL Database containing user Data.
        
### **OpenAI API Key**:
    
    *   Update the openai.api\_key in the script with your OpenAI API key.
    
### Dependencies

This project uses `poetry` for dependency management. Here’s how to set up the project:

```bash
# Install poetry
curl -sSL https://install.python-poetry.org | sh
```

# Clone the repository
```bash
git clone https://github.com/Siddharth-Dattaram-Pawar/InformaPDF-PDF_Extraction_And_Querying.git
cd InformaPDF-PDF_Extraction_And_Querying
```

# Install dependencies using poetry
```bash
poetry install
```

## Environment Setup
Ensure you have the necessary environment variables set up, especially for database connections and cloud services.

To install python-dotenv, use the following command:
```bash
poetry add python-dotenv
```

### Loading Environment Variables in Your Code

In your FastAPI or any Python application, you can load the environment variables from the `.env` file by adding the following lines in your code:

```python
from dotenv import load_dotenv
import os

# Load the environment variables from the .env file
load_dotenv()

# Access the environment variables
database_url = os.getenv('DATABASE_URL')
pdf_co_api_key = os.getenv('PDF_CO_API_KEY')
openai_api_key = os.getenv('OPENAI_API_KEY')
```

### Example Environment Variables

```bash
export DATABASE_URL="your_database_url"
export PDF_CO_API_KEY="your_pdf_co_api_key"
export OPENAI_API_KEY="your-openai-api-key"
```

## Running the Project

### Airflow Pipelines
To run the Airflow pipelines, navigate to the `airflow` directory and start the Airflow server:

```bash
cd airflow
airflow db init
airflow webserver -p 8080
airflow scheduler
```

## FastAPI Application

To run the FastAPI application, use the following command:

```bash
docker build -t gcr.io/[GCP_PROJECT_ID]/fastapi-app -f [FASTAPI_DOCKERFILE] .
docker push gcr.io/[GCP_PROJECT_ID]/fastapi-app
gcloud run deploy fastapi-service --image gcr.io/[GCP_PROJECT_ID]/fastapi-app --platform managed --region us-east1 --allow-unauthenticated --port 8000
```

## Streamlit Application
```bash
docker build -t gcr.io/[GCP_PROJECT_ID]/streamlit-app -f [STREAMLIT_DOCKERFILE] .
docker push gcr.io/[GCP_PROJECT_ID]/streamlit-app
gcloud run deploy streamlit-service --image gcr.io/[GCP_PROJECT_ID]/streamlit-app --platform managed --region us-east1 --allow-unauthenticated --port 8501
```

## Deployment

To deploy the applications to a public cloud platform using Docker Compose, follow these steps:

```bash
docker-compose build .
docker-compose up -d
```


## License
-------

MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
