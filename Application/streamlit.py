import streamlit as st
import requests
import os
import re
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load environment variables
API_URL: Optional[str] = os.getenv("API_URL")

if not API_URL:
    st.error("API_URL environment variable is not set. Please set it and restart the app.")
    st.stop()

# Set custom styles for the entire app
st.markdown(
    """
    <style>
    /* Set background color and padding for the entire app */
    .main {
        background-color: #F5F5F5; /* Light Gray */
        padding: 20px 50px 20px 50px; /* Top, Right, Bottom, Left padding */
    }

    /* Override background color and padding for all containers */
    .block-container {
        background-color: #F5F5F5;
        padding: 30px 40px 30px 40px; /* Top, Right, Bottom, Left padding */
    }

    /* Set font family to Clarendon for all text elements */
    body, h1, h2, h3, h4, h5, h6, label, p, div, .stAlert, .stTextInput, .stTextArea, .stSelectbox, .stNumberInput {
        font-family: 'Clarendon', serif !important;
        color: black !important;
        font-weight: normal !important; /* Make text not bold */
    }

    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>input, .stNumberInput>div>div>input {
        background-color: white !important;
        color: black !important;
        font-weight: normal !important; /* Make input text not bold */
    }

    /* Set button styles */
    .stButton button {
        background-color: #ADFF2F !important; /* Set button color to Green Yellow */
        color: white !important; /* Set button text color to white */
        font-family: 'Clarendon', serif !important; /* Set button text font to Clarendon */
        font-weight: normal !important; /* Make button text not bold */
        border-radius: 10px;
    }

    /* Set button hover effect */
    .stButton button:hover {
        background-color: #7FFF00 !important; /* Set hover color to Chartreuse */
    }

    /* Set sidebar background and text color */
    .css-1d391kg {
        background-color: #E5E7EB !important; /* Light shade of gray for the sidebar */
    }

    .css-1d391kg .css-2trqyj {
        color: black !important;
        font-family: 'Clarendon', serif !important; /* Set sidebar text font to Clarendon */
        font-weight: normal !important; /* Make sidebar text not bold */
    }

    /* Adjust text and heading styles */
    .main-title {
        font-family: 'Clarendon', serif !important; /* Set heading font to Clarendon */
        color: black !important;
        text-align: center;
        font-size: 40px;
        font-weight: bold !important; /* Keep heading bold */
    }

    /* Style for custom headings with underline and font size */
    .custom-heading {
        font-size: 18px !important;
        text-decoration: underline !important;
        font-family: 'Clarendon', serif !important;
        margin-top: 20px;
        margin-bottom: 10px;
    }

    /* Style for the logo in the top right */
    .logo-container {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        padding: 10px 0 10px 0; /* Top, Right, Bottom, Left padding */
    }
    .logo-image {
        height: 60px;
        margin-right: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Add the logo to the top right using the provided image URL
st.markdown(
    """
    <div class="logo-container">
        <img src="https://th.bing.com/th/id/OIP.WamLhKKDXEVGJ5mnAAaXRwAAAA?w=179&h=180&c=7&r=0&o=5&dpr=1.3&pid=1.7" class="logo-image" alt="Logo">
    </div>
    """,
    unsafe_allow_html=True,
)

# Custom main title with Clarendon font
st.markdown('<h1 class="main-title">InformaPDF</h1>', unsafe_allow_html=True)


def check_api_connection() -> bool:
    """
    Check if the API is accessible and responding.

    Returns:
        bool: True if the API is accessible, False otherwise.
    """
    try:
        response = requests.get(f"{API_URL}/health")
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as err:
        st.error(f"Error connecting to the API: {err}")
        return False


def get_token(username: str, password: str) -> Optional[str]:
    """
    Obtain a JWT token for the given username and password.

    Args:
        username (str): Username for authentication.
        password (str): Password for authentication.

    Returns:
        Optional[str]: JWT token if authentication is successful, None otherwise.
    """
    try:
        response = requests.post(f"{API_URL}/token", data={"username": username, "password": password})
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred: {str(e)}")
        return None


def register_user(username: str, password: str) -> Optional[str]:
    """
    Register a new user with the given username and password.

    Args:
        username (str): Username for the new user.
        password (str): Password for the new user.

    Returns:
        Optional[str]: JWT token if registration is successful, None otherwise.
    """
    try:
        response = requests.post(f"{API_URL}/register", json={"username": username, "password": password})
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        st.error(f"Registration failed: {str(e)}")
        return None


def is_valid_password(password: str) -> Optional[str]:
    """
    Validate the complexity of a password.

    Args:
        password (str): Password to validate.

    Returns:
        Optional[str]: Error message if the password is invalid, None otherwise.
    """
    if len(password) < 8:
        return "Password should be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return "Password should contain at least one uppercase letter"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return "Password should contain at least one special character"
    return None


def get_pdfs(token: str) -> List[str]:
    """
    Fetch the list of available PDFs.

    Args:
        token (str): JWT token for authentication.

    Returns:
        List[str]: List of PDF file names.
    """
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{API_URL}/pdfs", headers=headers)
        response.raise_for_status()
        return response.json().get("pdfs", [])
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch PDFs: {str(e)}")
        return []


def get_extract(token: str, pdf_name: str, extract_type: str) -> Optional[str]:
    """
    Fetch the extracted content of a PDF.

    Args:
        token (str): JWT token for authentication.
        pdf_name (str): Name of the PDF file.
        extract_type (str): Type of extraction to be used.

    Returns:
        Optional[str]: Extracted content of the PDF, or None if an error occurs.
    """
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{API_URL}/extract/{pdf_name}?extract_type={extract_type}", headers=headers)
        response.raise_for_status()
        return response.json().get("extract")
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch extract: {str(e)}")
        return None


def query_openai(token: str, pdf_name: str, extract_type: str, query: str) -> Optional[str]:
    """
    Send a query to OpenAI based on the extracted content of a PDF.

    Args:
        token (str): JWT token for authentication.
        pdf_name (str): Name of the PDF file.
        extract_type (str): Type of extraction used.
        query (str): Query to ask OpenAI.

    Returns:
        Optional[str]: OpenAI's response to the query, or None if an error occurs.
    """
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"pdf_name": pdf_name, "extract_type": extract_type, "query": query}
    try:
        response = requests.post(f"{API_URL}/query", headers=headers, json=payload)
        response.raise_for_status()
        return response.json().get("answer")
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while querying OpenAI: {str(e)}")
        return None


def main() -> None:
    """
    Main function to handle the Streamlit app logic.
    """
    # Check API connection
    if not check_api_connection():
        st.error("Unable to connect to the API. Please check your internet connection and API status.")
        st.stop()

    # Initialize session state variables
    if 'token' not in st.session_state:
        st.session_state.token = None
    if 'extract_type' not in st.session_state:
        st.session_state.extract_type = None
    if 'extract_content' not in st.session_state:
        st.session_state.extract_content = None
    if 'query_response' not in st.session_state:
        st.session_state.query_response = None

    # User authentication: Login and Register tabs
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
                    st.rerun()
        
        with tab2:
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type='password')
            confirm_password = st.text_input("Confirm Password", type='password')
            
            if st.button("Register"):
                # Password validation
                password_error = is_valid_password(new_password)
                if password_error:
                    st.error(password_error)
                elif new_password != confirm_password:
                    st.error("Confirm Password does not match the Entered Password!")
                else:
                    token = register_user(new_username, new_password)
                    if token:
                        st.session_state.token = token
                        st.success("Registered and logged in successfully!")
                        st.rerun()

    else:
        st.sidebar.success("Logged in successfully!")
        if st.sidebar.button("Logout"):
            st.session_state.token = None
            st.session_state.extract_type = None  # Reset extract_type on logout
            st.session_state.extract_content = None  # Reset extract_content on logout
            st.session_state.query_response = None  # Reset query_response on logout
            st.rerun()

        # Display underlined and formatted headings
        st.markdown('<div class="custom-heading">Select a PDF</div>', unsafe_allow_html=True)
        pdfs = get_pdfs(st.session_state.token)
        if pdfs:
            selected_pdf = st.selectbox("", pdfs)  # Use an empty label since we have a custom heading above
            if selected_pdf:
                pdf_name = selected_pdf.split('/')[-1]  # Get just the filename
                st.markdown(f'<div class="custom-heading">You selected: {pdf_name}</div>', unsafe_allow_html=True)

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("Extract using PyPDF🔍"):
                        st.session_state.extract_type = "pypdf"  # Set the extraction type
                        st.session_state.extract_content = get_extract(st.session_state.token, pdf_name, st.session_state.extract_type)
                        st.session_state.query_response = None  # Reset query_response on new extraction
                        if st.session_state.extract_content:
                            st.success("Extracted the PDF using PyPDF✅")  # Added green tick mark emoji
                            # Display only the first 10 lines of the extracted content
                            preview = "\n".join(st.session_state.extract_content.splitlines()[:10])
                            with st.expander("Extract Preview", expanded=True):
                                st.write(preview)

                with col2:
                    if st.button("Extract using PDF.CO✒️"):
                        st.session_state.extract_type = "pdfco"  # Set the extraction type
                        st.session_state.extract_content = get_extract(st.session_state.token, pdf_name, st.session_state.extract_type)
                        st.session_state.query_response = None  # Reset query_response on new extraction
                        if st.session_state.extract_content:
                            st.success("Extracted the PDF using PDF.CO✅")  # Added green tick mark emoji
                            # Display only the first 10 lines of the extracted content
                            preview = "\n".join(st.session_state.extract_content.splitlines()[:10])
                            with st.expander("Extract Preview", expanded=True):
                                st.write(preview)

                st.markdown('<div class="custom-heading">Enter your query</div>', unsafe_allow_html=True)
                user_query = st.text_input("")

                # Display "Generate Response" button directly
                if st.button("Generate Response"):
                    if st.session_state.extract_type is not None:  # Ensure extract_type is set
                        if user_query:
                            # Query OpenAI and store the response
                            st.session_state.query_response = query_openai(st.session_state.token, pdf_name, st.session_state.extract_type, user_query)
                            if st.session_state.query_response:
                                st.write("### OpenAI's Response")
                                st.write(st.session_state.query_response)

                # Show "Ask Another Query" button only after a response is displayed
                if st.session_state.query_response:
                    if st.button("Ask Another Query"):
                        st.session_state.query_response = None  # Reset query_response for a new query
                        st.rerun()

if __name__ == "__main__":
    main()
