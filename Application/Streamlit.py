import streamlit as st
import requests
import os
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
import re
 
# Load environment variables from .env file
load_dotenv()
 
# Load environment variables
API_URL = os.getenv("API_URL")
 
if not API_URL:
    st.error("API_URL environment variable is not set. Please set it and restart the app.")
    st.stop()
 
def check_api_connection() -> bool:
    """Check if the API connection is successful."""
    try:
        response = requests.get(f"{API_URL}/health")
        response.raise_for_status()
        return True
    except requests.exceptions.HTTPError as http_err:
        st.error(f"HTTP error occurred: {http_err}")  # Detailed error message
    except requests.exceptions.ConnectionError as conn_err:
        st.error(f"Connection error occurred: {conn_err}")  # Connection issues
    except requests.exceptions.Timeout as timeout_err:
        st.error(f"Timeout error occurred: {timeout_err}")  # Timeout issues
    except requests.exceptions.RequestException as err:
        st.error(f"An error occurred: {err}")  # Other errors
    return False
 
def get_token(username: str, password: str) -> Optional[str]:
    """Retrieve the authentication token for a user."""
    try:
        response = requests.post(
            f"{API_URL}/token",
            data={"username": username, "password": password}
        )
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            st.error("Invalid username or password")
        else:
            st.error(f"An error occurred: {str(e)}")
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred: {str(e)}")
    return None
 
def register_user(username: str, password: str) -> Optional[str]:
    """Register a new user and return the authentication token."""
    try:
        response = requests.post(
            f"{API_URL}/register",
            json={"username": username, "password": password}
        )
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            st.error("Username already exists, enter a new username!")
        else:
            st.error(f"Registration failed: {str(e)}")
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred: {str(e)}")
    return None
 
def validate_password(password: str) -> bool:
    """Validate password complexity."""
    if (len(password) < 8 or
        not re.search(r"[A-Z]", password) or  # At least one uppercase letter
        not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password) or  # At least one special character
        " " in password):  # No spaces
        return False
    return True
 
def get_pdfs(token: str) -> List[str]:
    """Retrieve a list of PDFs from the API."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{API_URL}/pdfs", headers=headers)
        response.raise_for_status()
        return response.json().get("pdfs", [])
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            st.error("Session expired. Please log in again.")
            st.session_state.token = None
        else:
            st.error(f"Failed to fetch PDFs: {str(e)}")
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred: {str(e)}")
    return []
 
def get_extract(token: str, pdf_name: str, extract_type: str) -> Optional[str]:
    """Retrieve the extract of a specified PDF."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{API_URL}/extract/{pdf_name}?extract_type={extract_type}", headers=headers)
        response.raise_for_status()
        return response.json().get("extract")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            st.error("Session expired. Please log in again.")
            st.session_state.token = None
        elif e.response.status_code == 404:
            st.error("Extract not found")
        else:
            st.error(f"Failed to fetch extract: {str(e)}")
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred: {str(e)}")
    return None
 
def query_openai(token: str, pdf_name: str, extract_type: str, query: str) -> Optional[str]:
    """Send a query to OpenAI based on the extracted text from a PDF."""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"pdf_name": pdf_name, "extract_type": extract_type, "query": query}
   
    try:
        response = requests.post(
            f"{API_URL}/query",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json().get("answer")
    except requests.exceptions.HTTPError as e:
        st.error(f"An error occurred: {e.response.status_code} - {e.response.text}")  # Log detailed error
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while querying OpenAI: {str(e)}")
    return None
 
def main() -> None:
    """Main function to run the Streamlit application."""
    st.title("InformaPDF")
 
    if not check_api_connection():
        st.error("Unable to connect to the API. Please check your internet connection and API status.")
        st.stop()
 
    if 'token' not in st.session_state:
        st.session_state.token = None
 
    # Initialize extract_type in session state
    if 'extract_type' not in st.session_state:
        st.session_state.extract_type = None
 
    if st.session_state.token is None:
        tab1, tab2 = st.tabs(["Login", "Register"])
       
        with tab1:
            username = st.text_input("Username")
            password = st.text_input("Password", type='password')
           
            if st.button("Login", key="login_button"):
                token = get_token(username, password)
                if token:
                    st.session_state.token = token
                    st.success("Logged in successfully!")
                    st.rerun()
       
        with tab2:
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type='password')
            confirm_password = st.text_input("Confirm Password", type='password')
           
            if st.button("Register", key="register_button"):
                if new_password != confirm_password:
                    st.error("Confirmed Password does not match the entered Password!")
                elif not validate_password(new_password):
                    st.error("Password must be at least 8 characters long, contain at least 1 capital letter, 1 special character, and should not contain spaces.")
                else:
                    token = register_user(new_username, new_password)
                    if token:
                        st.session_state.token = token
                        st.success("Registered and logged in successfully!")
                        st.rerun()
 
    else:
        st.sidebar.success("Logged in successfully!")
        if st.sidebar.button("Logout", key="logout_button",
                             help="Log out of the application",
                             style={"background-color": "red", "color": "white"}):
            st.session_state.token = None
            st.session_state.extract_type = None  # Reset extract_type on logout
            st.rerun()
 
        pdfs = get_pdfs(st.session_state.token)
        if pdfs:
            selected_pdf = st.selectbox("Select a PDF", pdfs)
            if selected_pdf:
                pdf_name = selected_pdf.split('/')[-1]  # Get just the filename
                st.write(f"You selected: {pdf_name} from the folder")
 
                col1, col2 = st.columns(2)
 
                with col1:
                    if st.button("Extract using PyPDF🔍", key="extract_pypdf",
                                 help="Extract using PyPDF method",
                                 style={"background-color": "#AAFF00", "color": "black"}):
                        st.session_state.extract_type = "pypdf"  # Set the extraction type
 
                with col2:
                    if st.button("Extract using PDF.CO🖋", key="extract_pdfco",
                                 help="Extract using PDF.CO method",
                                 style={"background-color": "#AAFF00", "color": "black"}):
                        st.session_state.extract_type = "pdfco"  # Set the extraction type
 
                st.write("### Ask a Question about the Extract")
                user_query = st.text_input("Enter your query:")
                if user_query:
                    if st.session_state.extract_type is not None:  # Ensure extract_type is set
                        if st.button("Generate Response", key="generate_response",
                                     style={"background-color": "#AAFF00", "color": "black"}):
                            answer = query_openai(st.session_state.token, pdf_name, st.session_state.extract_type, user_query)  # Use dynamic extract_type
                            if answer:
                                st.write("### OpenAI's Response")
                                st.write(answer)
                    else:
                        st.error("Please select an extraction method before submitting your query.")
 
                # Button to ask another query
                if st.button("Ask Another Query", key="ask_another_query"):
                    st.session_state.extract_type = None  # Reset extract_type for a new query
                    st.rerun()
 
if __name__ == "__main__":
    main()