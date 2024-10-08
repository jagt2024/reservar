import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.transport.urllib3 import AuthorizedHttp
from urllib3.util.retry import Retry
from urllib3.exceptions import MaxRetryError

class CustomGspread(gspread.Client):
    def __init__(self, auth, timeout=30, retries=3):
        super().__init__(auth)
        self.timeout = timeout
        self.retries = retries

    def request(self, *args, **kwargs):
        retry = Retry(total=self.retries, backoff_factor=0.5)
        kwargs.setdefault('timeout', self.timeout)
        authorized_http = AuthorizedHttp(self.auth, refresh_timeout=self.timeout)
        authorized_http.retries = retry
        return authorized_http.request(*args, **kwargs)

class SheetHandler:
    def __init__(self, credentials, document, timeout=30, retries=3):
        self.credentials = credentials
        self.document = document
        self.timeout = timeout
        self.retries = retries
        self.gc = None
        self.sh = None
        self.connect()

    def connect(self):
        try:
            creds = Credentials.from_authorized_user_info(self.credentials)
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    raise ValueError("Invalid credentials")

            self.gc = CustomGspread(creds, timeout=self.timeout, retries=self.retries)
            self.sh = self.gc.open(self.document)
        except MaxRetryError:
            st.error("Couldn't connect to Google Sheets after multiple attempts. Please check your internet connection and try again.")
        except Exception as e:
            st.error(f"An error occurred while connecting to Google Sheets: {str(e)}")

# Uso
credentials = st.secrets["gcp_service_account"]
document = "Your Google Sheet Name"

sheet_handler = SheetHandler(credentials, document, timeout=60, retries=3)

if sheet_handler.sh:
    # Ahora puedes usar sheet_handler.sh para interactuar con tu hoja de cálculo
    worksheet = sheet_handler.sh.worksheet("Sheet1")
    data = worksheet.get_all_values()
    st.write(data)