import os
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, constr
from google.cloud import storage
from google.oauth2 import service_account
import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error
import openai
from dotenv import load_dotenv
from typing import Optional, Dict, Any
 
load_dotenv()
 
app = FastAPI()
 
# Load environment variables
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
BUCKET_NAME = os.getenv("GCP_BUCKET_NAME")
GCP_CREDENTIALS_PATH = os.getenv("GCP_CREDENTIALS_PATH")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
 
# MySQL Database configuration
DB_CONFIG = {
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
    print(f"Error setting up GCP Storage client: {str(e)}")
    raise
 
class UserCreate(BaseModel):
    username: str
    password: constr(min_length=8)  # At least 8 characters
 
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
 
def get_db_connection() -> Optional[mysql.connector.connection.MySQLConnection]:
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        return None
 
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
 
def get_user(username: str) -> Optional[UserInDB]:
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
 
def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
 
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
 
async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
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
 
def is_valid_password(password: str) -> bool:
    """Check password constraints."""
    return (
        len(password) >= 8 and
        any(char.isupper() for char in password) and  # At least one capital letter
        any(char in "!@#$%^&*(),.?\":{}|<>" for char in password) and  # At least one special character
        " " not in password  # No spaces
    )
 
@app.post("/register", response_model=Token)
async def register(user: UserCreate) -> Token:
    if not is_valid_password(user.password):
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long, contain at least 1 capital letter, 1 special character, and should not contain spaces.")
   
    db_user = get_user(user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already exists, enter a new username!")
 
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
 
@app.get("/pdfs")
async def get_pdfs(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        bucket = storage_client.get_bucket(BUCKET_NAME)
        pdf_list = set()  # Using a set to avoid duplicates
 
        pdf_folder = os.getenv('GCP_PDF_FOLDER', 'pdfs/')
        pypdf_folder = os.getenv('GCP_PYPDF_EXTRACT_FOLDER', 'pypdf_extracts/')
        pdfco_folder = os.getenv('GCP_PDFCO_EXTRACT_FOLDER', 'pdfco_extracts/')
 
        def list_pdfs_from_folder(folder: str) -> None:
            try:
                for subfolder in ['test', 'validation']:
                    blobs = bucket.list_blobs(prefix=f"{folder}{subfolder}/")
                    for blob in blobs:
                        if blob.name.lower().endswith('.pdf'):
                            pdf_list.add(f"{subfolder}/{blob.name.split('/')[-1]}")
                        elif blob.name.lower().endswith('_extract.txt'):
                            pdf_name = blob.name.split('/')[-1].replace('_extract.txt', '.pdf')
                            pdf_list.add(f"{subfolder}/{pdf_name}")
            except Exception as e:
                print(f"Error listing PDFs from folder {folder}: {str(e)}")
 
        list_pdfs_from_folder(pdf_folder)
        list_pdfs_from_folder(pypdf_folder)
        list_pdfs_from_folder(pdfco_folder)
 
        return {"pdfs": list(pdf_list)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching PDFs: {str(e)}")
 
@app.get("/extract/{pdf_name}")
async def get_extract(pdf_name: str, extract_type: str, current_user: dict = Depends(get_current_user)) -> Dict[str, str]:
    if extract_type not in ["pypdf", "pdfco"]:
        raise HTTPException(status_code=400, detail="Invalid extract type")
   
    extract = get_pdf_extract(pdf_name, extract_type)
    if extract is None:
        raise HTTPException(status_code=404, detail="Extract not found")
   
    return {"extract": extract}
 
@app.post("/query")
async def query_openai(payload: QueryPayload) -> Dict[str, str]:
    extract = get_pdf_extract(payload.pdf_name, payload.extract_type)
    if extract is None:
        raise HTTPException(status_code=404, detail="Extract not found")
 
    try:
        response = openai.ChatCompletion.create(
             model="gpt-3.5-turbo",
             messages=[{"role": "user", "content": f"Based on the following text, answer the query:\n\n{extract}\n\nQuery: {payload.query}"}],
             max_tokens=150
        )
       
        answer = response.choices[0].message['content'].strip()
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying OpenAI: {str(e)}")
 
@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "healthy"}
 