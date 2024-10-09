import streamlit as st
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL")

if not API_URL:
    st.error("API_URL environment variable is not set. Please set it and restart the app.")
    st.stop()

def check_api_connection():
    try:
        response = requests.get(f"{API_URL}/health")
        response.raise_for_status()
        return True
    except:
        return False

def get_token(username, password):
    try:
        response = requests.post(
            f"{API_URL}/token",
            data={"username": username, "password": password}
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            st.error("Invalid username or password")
        else:
            st.error(f"An error occurred: {str(e)}")
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred: {str(e)}")
    return None

def register_user(username, password):
    try:
        response = requests.post(
            f"{API_URL}/register",
            json={"username": username, "password": password}
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            st.error("Username already exists")
        else:
            st.error(f"Registration failed: {str(e)}")
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred: {str(e)}")
    return None

def get_pdfs(token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{API_URL}/pdfs", headers=headers)
        response.raise_for_status()
        return response.json()["pdfs"]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            st.error("Session expired. Please log in again.")
            st.session_state.token = None
        else:
            st.error(f"Failed to fetch PDFs: {str(e)}")
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred: {str(e)}")
    return []

def get_extract(token, pdf_name, extract_type):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{API_URL}/extract/{pdf_name}?extract_type={extract_type}", headers=headers)
        response.raise_for_status()
        return response.json()["extract"]
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

def main():
    st.title("PDF Extractor Application")

    if not check_api_connection():
        st.error("Unable to connect to the API. Please check your internet connection and API status.")
        st.stop()

    if 'token' not in st.session_state:
        st.session_state.token = None

    if st.session_state.token is None:
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            username = st.text_input("Username")
            password = st.text_input("Password", type='password')
            
            if st.button("Login"):
                token = get_token(username, password)
                if token:
                    st.session_state.token = token
                    st.success("Logged in successfully!")
                    st.experimental_rerun()
        
        with tab2:
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type='password')
            confirm_password = st.text_input("Confirm Password", type='password')
            
            if st.button("Register"):
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    token = register_user(new_username, new_password)
                    if token:
                        st.session_state.token = token
                        st.success("Registered and logged in successfully!")
                        st.experimental_rerun()

    else:
        st.sidebar.success("Logged in successfully!")
        if st.sidebar.button("Logout"):
            st.session_state.token = None
            st.experimental_rerun()

        pdfs = get_pdfs(st.session_state.token)
        if pdfs:
            selected_pdf = st.selectbox("Select a PDF", pdfs)
            if selected_pdf:
                subfolder, pdf_name = selected_pdf.split('/', 1)
                st.write(f"You selected: {pdf_name} from {subfolder} folder")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Extract using PyPDF"):
                        extract = get_extract(st.session_state.token, selected_pdf, "pypdf")
                        if extract:
                            st.text_area("Extracted Content (PyPDF)", extract, height=300)
                
                with col2:
                    if st.button("Extract using PDF.co"):
                        extract = get_extract(st.session_state.token, selected_pdf, "pdfco")
                        if extract:
                            st.text_area("Extracted Content (PDF.co)", extract, height=300)
        else:
            st.warning("No PDFs available. Please check your GCP bucket or contact the administrator.")

if __name__ == '__main__':
    main()