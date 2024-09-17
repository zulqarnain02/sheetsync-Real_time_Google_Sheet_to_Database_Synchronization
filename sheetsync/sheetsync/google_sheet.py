import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Path to the service account credentials JSON file
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), 'google_credentials', 'credentials.json')

# Define the Google Sheets API scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def get_google_sheets_service():
    """Load service account credentials and return a Google Sheets API service."""
    
    # Load the service account credentials from the file
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    
    # Build the service for Google Sheets
    service = build('sheets', 'v4', credentials=creds)
    return service
