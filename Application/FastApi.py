import os
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

app = FastAPI()

# Load environment variables
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
BUCKET_NAME = os.getenv("GCP_BUCKET_NAME")
PDF_FOLDER = os.getenv("GCP_PDF_FOLDER", "pdfs/")
GCP_CREDENTIALS_PATH = os.getenv("GCP_CREDENTIALS_PATH")

# MySQL Database configuration
DB_CONFIG = {
    'host': os.getenv('GCP_DB_HOST'),
    'database': os.getenv('GCP_DB_NAME'),
    'user': os.getenv('GCP_DB_USER'),
    'password': os.getenv('GCP_DB_PASSWORD')
}

# Validate required environment variables
if not all([SECRET_KEY, BUCKET_NAME, GCP_CREDENTIALS_PATH] + list(DB_CONFIG.values())):
    raise ValueError("Missing required environment variables")

# Set up Storage client
try:
    credentials = service_account.Credentials.from_service_account_file(GCP_CREDENTIALS_PATH)
    storage_client = storage.Client(credentials=credentials)
except Exception as e:
    print(f"Error setting up GCP Storage client: {str(e)}")
    raise

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class UserCreate(BaseModel):
    username: str
    password: str

class UserInDB(UserCreate):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        return None

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_user(username: str):
    connection = get_db_connection()
    if connection is None:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT username, password as hashed_password FROM users WHERE username = %s"
        cursor.execute(query, (username,))
        user = cursor.fetchone()
        if user:
            return UserInDB(**user)
    except Error as e:
        print(f"Error fetching user from database: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return None

def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_pdf_extract(pdf_name: str, extract_type: str):
    if extract_type == "pypdf":
        base_folder = os.getenv('GCP_PYPDF_EXTRACT_FOLDER')
    elif extract_type == "pdfco":
        base_folder = os.getenv('GCP_PDFCO_EXTRACT_FOLDER')
    else:
        raise ValueError("Invalid extract type")

    bucket = storage_client.get_bucket(BUCKET_NAME)
    
    for subfolder in ['test', 'validation']:
        blob_name = f"{base_folder}{subfolder}/{pdf_name.replace('.pdf', '_extract.txt')}"
        blob = bucket.blob(blob_name)
        
        if blob.exists():
            return blob.download_as_text()
    
    # If the extract is not found in either subfolder
    return None

async def get_current_user(token: str = Depends(oauth2_scheme)):
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

@app.post("/register", response_model=Token)
async def register(user: UserCreate):
    db_user = get_user(user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
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
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
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

@app.get("/pdfs")
async def get_pdfs(current_user: dict = Depends(get_current_user)):
    try:
        bucket = storage_client.get_bucket(BUCKET_NAME)
        pdf_list = set()  # Using a set to avoid duplicates

        pdf_folder = os.getenv('GCP_PDF_FOLDER')
        pypdf_folder = os.getenv('GCP_PYPDF_EXTRACT_FOLDER')
        pdfco_folder = os.getenv('GCP_PDFCO_EXTRACT_FOLDER')

        # Function to list PDFs from a folder
        def list_pdfs_from_folder(folder):
            for subfolder in ['test', 'validation']:
                blobs = bucket.list_blobs(prefix=f"{folder}{subfolder}/")
                for blob in blobs:
                    if blob.name.lower().endswith('.pdf'):
                        pdf_list.add(f"{subfolder}/{blob.name.split('/')[-1]}")
                    elif blob.name.lower().endswith('_extract.txt'):
                        pdf_name = blob.name.split('/')[-1].replace('_extract.txt', '.pdf')
                        pdf_list.add(f"{subfolder}/{pdf_name}")

        # List PDFs from all relevant folders
        list_pdfs_from_folder(pdf_folder)
        list_pdfs_from_folder(pypdf_folder)
        list_pdfs_from_folder(pdfco_folder)

        return {"pdfs": list(pdf_list)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching PDFs: {str(e)}")

@app.get("/extract/{pdf_name}")
async def get_extract(pdf_name: str, extract_type: str, current_user: dict = Depends(get_current_user)):
    if extract_type not in ["pypdf", "pdfco"]:
        raise HTTPException(status_code=400, detail="Invalid extract type")
    
    extract = get_pdf_extract(pdf_name, extract_type)
    if extract is None:
        raise HTTPException(status_code=404, detail="Extract not found")
    
    return {"extract": extract}