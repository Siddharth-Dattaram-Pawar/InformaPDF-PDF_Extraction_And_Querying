import os
from typing import Optional, List, Dict, Union
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from google.cloud import storage
from google.oauth2 import service_account
import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error
import openai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Load environment variables
SECRET_KEY: Optional[str] = os.getenv("SECRET_KEY")
ALGORITHM: Optional[str] = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
BUCKET_NAME: Optional[str] = os.getenv("GCP_BUCKET_NAME")
GCP_CREDENTIALS_PATH: Optional[str] = os.getenv("GCP_CREDENTIALS_PATH")
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")

# MySQL Database configuration
DB_CONFIG: Dict[str, Optional[str]] = {
    'host': os.getenv('GCP_DB_HOST'),
    'database': os.getenv('GCP_DB_NAME'),
    'user': os.getenv('GCP_DB_USER'),
    'password': os.getenv('GCP_DB_PASSWORD')
}

# OpenAI API setup
openai.api_key = OPENAI_API_KEY

# OAuth2 for token handling
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Validate required environment variables
if not all([SECRET_KEY, BUCKET_NAME, GCP_CREDENTIALS_PATH] + list(DB_CONFIG.values())):
    raise ValueError("Missing required environment variables")

# Set up Google Cloud Storage client
try:
    credentials = service_account.Credentials.from_service_account_file(GCP_CREDENTIALS_PATH)
    storage_client = storage.Client(credentials=credentials)
except Exception as e:
    raise RuntimeError(f"Error setting up GCP Storage client: {str(e)}")

# Pydantic models
class UserCreate(BaseModel):
    username: str
    password: str

class UserInDB(BaseModel):
    username: str
    hashed_password: str  # Keep this field for authentication

class Token(BaseModel):
    access_token: str
    token_type: str

class QueryPayload(BaseModel):
    pdf_name: str
    extract_type: str
    query: str

# Utility functions
def get_db_connection() -> Optional[mysql.connector.connection.MySQLConnection]:
    """
    Establish a connection to the MySQL database.
    
    Returns:
        mysql.connector.connection.MySQLConnection: A connection to the MySQL database if successful, None otherwise.
    """
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        return None

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify if the provided plain password matches the hashed password.

    Args:
        plain_password (str): The plain text password.
        hashed_password (str): The hashed password stored in the database.

    Returns:
        bool: True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_user(username: str) -> Optional[UserInDB]:
    """
    Retrieve a user by their username from the database.

    Args:
        username (str): The username to look up.

    Returns:
        Optional[UserInDB]: A user object if the user is found, None otherwise.
    """
    connection = get_db_connection()
    if connection is None:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT username, password as hashed_password FROM users WHERE username = %s"
        cursor.execute(query, (username,))
        user = cursor.fetchone()
        if user:
            return UserInDB(**user)  # This will now correctly match the fields
    except Error as e:
        print(f"Error fetching user from database: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return None

def authenticate_user(username: str, password: str) -> Union[bool, UserInDB]:
    """
    Authenticate a user by username and password.

    Args:
        username (str): The username for authentication.
        password (str): The password for authentication.

    Returns:
        Union[bool, UserInDB]: The authenticated user object if successful, False otherwise.
    """
    user = get_user(username)
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data (dict): The data to encode in the token.
        expires_delta (Optional[timedelta]): The expiration time delta.

    Returns:
        str: The encoded JWT token.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta if expires_delta else datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """
    Get the current authenticated user from the JWT token.

    Args:
        token (str): The JWT token provided by the client.

    Returns:
        UserInDB: The current authenticated user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(username)
    if user is None:
        raise credentials_exception
    return user

def get_pdf_extract(pdf_name: str, extract_type: str) -> Optional[str]:
    """
    Retrieve the extracted content of a PDF from Google Cloud Storage.

    Args:
        pdf_name (str): The name of the PDF file.
        extract_type (str): The type of extraction (e.g., "pypdf", "pdfco").

    Returns:
        Optional[str]: The extracted content as a string, or None if not found.
    """
    base_folder = os.getenv(f'GCP_{extract_type.upper()}_EXTRACT_FOLDER', 'extracts/')
    bucket = storage_client.get_bucket(BUCKET_NAME)

    for subfolder in ['test', 'validation']:
        blob_name = f"{base_folder}{subfolder}/{pdf_name.replace('.pdf', '.txt')}"
        blob = bucket.blob(blob_name)

        if blob.exists():
            return blob.download_as_text()
    return None

# API Endpoints
@app.post("/register", response_model=Token)
async def register(user: UserCreate) -> Token:
    """Register a new user in the system."""
    db_user = get_user(user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already exists, Please choose a new Username!")

    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())

    connection = get_db_connection()
    if connection is None:
        raise HTTPException(status_code=500, detail="Database connection error")

    try:
        cursor = connection.cursor()
        query = "INSERT INTO users (username, password) VALUES (%s, %s)"
        cursor.execute(query, (user.username, hashed_password.decode('utf-8')))
        connection.commit()
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/pdfs", response_model=Dict[str, List[str]])
async def get_pdfs(current_user: UserInDB = Depends(get_current_user)) -> Dict[str, List[str]]:
    try:
        bucket = storage_client.get_bucket(BUCKET_NAME)
        pdf_list: set = set()  # Using a set to avoid duplicates

        pdf_folder = os.getenv('GCP_PDF_FOLDER', 'pdfs/')
        pypdf_folder = os.getenv('GCP_PYPDF_EXTRACT_FOLDER', 'pypdf_extracts/')
        pdfco_folder = os.getenv('GCP_PDFCO_EXTRACT_FOLDER', 'pdfco_extracts/')

        def list_pdfs_from_folder(folder: str) -> None:
            for subfolder in ['test', 'validation']:
                blobs = bucket.list_blobs(prefix=f"{folder}{subfolder}/")
                for blob in blobs:
                    if blob.name.lower().endswith('.pdf'):
                        pdf_list.add(f"{subfolder}/{blob.name.split('/')[-1]}")
                    elif blob.name.lower().endswith('_extract.txt'):
                        pdf_name = blob.name.split('/')[-1].replace('_extract.txt', '.pdf')
                        pdf_list.add(f"{subfolder}/{pdf_name}")

        list_pdfs_from_folder(pdf_folder)
        list_pdfs_from_folder(pypdf_folder)
        list_pdfs_from_folder(pdfco_folder)

        return {"pdfs": list(pdf_list)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching PDFs: {str(e)}")

@app.get("/extract/{pdf_name}", response_model=Dict[str, str])
async def get_extract(pdf_name: str, extract_type: str, current_user: UserInDB = Depends(get_current_user)) -> Dict[str, str]:
    if extract_type not in ["pypdf", "pdfco"]:
        raise HTTPException(status_code=400, detail="Invalid extract type")

    extract = get_pdf_extract(pdf_name, extract_type)
    if extract is None:
        raise HTTPException(status_code=404, detail="Extract not found")

    return {"extract": extract}

@app.post("/query", response_model=Dict[str, str])
async def query_openai(payload: QueryPayload, current_user: UserInDB = Depends(get_current_user)) -> Dict[str, str]:
    extract = get_pdf_extract(payload.pdf_name, payload.extract_type)
    if extract is None:
        raise HTTPException(status_code=404, detail="Extract not found")

    try:
        response = openai.ChatCompletion.create(
             model="gpt-3.5-turbo",
             messages=[
                {"role": "user", "content": f"Based on the following text, answer the query:\n\n{extract}\n\nQuery: {payload.query}"}
            ],
            max_tokens=150
        )
        answer = response.choices[0].message['content'].strip()
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying OpenAI: {str(e)}")

@app.get("/health", response_model=Dict[str, str])
async def health_check() -> Dict[str, str]:
    return {"status": "healthy"}
