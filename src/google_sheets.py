# =============================================================
# src/google_sheets.py
#
# PURPOSE:
#   This module handles all communication with Google Sheets.
#   It can read data from a spreadsheet, which we later use
#   as the "knowledge base" for our RAG system.
#
# WHAT IS A MODULE?
#   A module is just a Python file. By putting related code
#   in separate files (modules), we keep our project organized.
#   Each module has one clear job.
#
# HOW GOOGLE SHEETS API WORKS:
#   1. You create a project in Google Cloud Console
#   2. Enable the Google Sheets API
#   3. Create credentials (service account or OAuth)
#   4. Share your sheet with the service account email
#   5. Use this code to read/write data
# =============================================================

# --- Standard library imports (built into Python) ---
import os           # For reading environment variables and file paths
import logging      # For printing helpful messages about what the code is doing

# --- Third-party imports (installed via pip) ---
import gspread                              # Google Sheets library
from google.oauth2.service_account import Credentials   # For service account auth
from google.oauth2.credentials import Credentials as OAuthCredentials
from google_auth_oauthlib.flow import InstalledAppFlow  # For OAuth login flow
from google.auth.transport.requests import Request       # For refreshing tokens
from dotenv import load_dotenv              # For loading .env file
import pickle                               # For saving/loading login tokens

# Load environment variables from .env file
# This MUST be called before reading os.environ variables
load_dotenv()

# Set up logging — this lets us print messages with timestamps and log levels
# instead of using plain print() statements
# LOG LEVELS (from least to most severe): DEBUG, INFO, WARNING, ERROR, CRITICAL
logger = logging.getLogger(__name__)


# =============================================================
# SCOPES — what permissions we're asking Google for
#
# These URLs tell Google what we're allowed to do.
# Using "readonly" is safer — we only need to READ the sheet,
# not write to it.
# =============================================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",  # Read sheets
    "https://www.googleapis.com/auth/drive.readonly",          # Read drive files
]


class GoogleSheetsConnector:
    """
    Connects to Google Sheets and reads data from it.

    WHAT IS A CLASS?
        A class is a blueprint for creating objects.
        An object bundles together data (attributes) and
        functions (methods) that work on that data.

    EXAMPLE USAGE:
        connector = GoogleSheetsConnector()
        data = connector.get_all_rows("Sheet1")
        text = connector.get_all_text()
    """

    def __init__(self):
        """
        __init__ is the constructor — it runs automatically when you
        create a new GoogleSheetsConnector() object.

        Here we:
        1. Read config from environment variables
        2. Authenticate with Google
        3. Open the spreadsheet
        """
        # Read configuration from environment variables
        # os.environ.get("KEY", "default") returns "default" if KEY is not set
        self.sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
        self.auth_method = os.environ.get("GOOGLE_AUTH_METHOD", "service_account")
        self.credentials_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")

        # These will be set after authentication
        self.client = None      # The gspread client object
        self.spreadsheet = None # The opened spreadsheet object

        # Authenticate and connect
        self._authenticate()

    def _authenticate(self):
        """
        Private method to authenticate with Google.

        The underscore prefix (_authenticate) is a Python convention
        meaning "this method is for internal use, not for outside code."

        WE SUPPORT TWO AUTH METHODS:
        1. Service Account — best for servers/automation
           - Create a service account in Google Cloud
           - Download the JSON key file
           - Share your sheet with the service account email
        2. OAuth — best for personal use on your computer
           - Opens a browser window to log in
           - Saves a token file so you don't log in every time
        """
        logger.info(f"Authenticating with Google using method: {self.auth_method}")

        if self.auth_method == "service_account":
            # --- Service Account Authentication ---
            # Service accounts are like robot users with an email address.
            # You share your Google Sheet with this email, and the code
            # logs in as that robot.
            credentials = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=SCOPES
            )

        elif self.auth_method == "oauth":
            # --- OAuth Authentication ---
            # This opens a browser for you to log in with your Google account.
            # After login, it saves a token.json file so you stay logged in.
            credentials = self._get_oauth_credentials()

        else:
            raise ValueError(
                f"Unknown auth method: '{self.auth_method}'. "
                "Use 'service_account' or 'oauth'."
            )

        # Create the gspread client with our credentials
        # gspread.authorize() wraps the credentials in a client object
        self.client = gspread.authorize(credentials)

        # Open the spreadsheet by its ID
        # The ID is the long string in the Google Sheets URL
        logger.info(f"Opening spreadsheet with ID: {self.sheet_id}")
        self.spreadsheet = self.client.open_by_key(self.sheet_id)
        logger.info("Successfully connected to Google Sheets!")

    def _get_oauth_credentials(self):
        """
        Handles the OAuth login flow for personal use.

        OAUTH FLOW EXPLAINED:
        1. First time: opens browser → you log in → Google gives us a token
        2. Next times: loads saved token from token.json
        3. If token is expired: automatically refreshes it
        """
        credentials = None

        # Check if we have a saved token from a previous login
        if os.path.exists("token.json"):
            # pickle.load reads a Python object that was previously saved to a file
            with open("token.json", "rb") as token_file:
                credentials = pickle.load(token_file)

        # If no token, or token is expired and can't be refreshed, log in again
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                # Token exists but is expired — refresh it automatically
                credentials.refresh(Request())
            else:
                # No token — open browser for login
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path,
                    SCOPES
                )
                # run_local_server opens a browser window and waits for login
                credentials = flow.run_local_server(port=0)

            # Save the new/refreshed token for next time
            with open("token.json", "wb") as token_file:
                pickle.dump(credentials, token_file)

        return credentials

    def get_all_rows(self, sheet_name: str = None) -> list[dict]:
        """
        Reads all rows from a worksheet as a list of dictionaries.

        PARAMETERS:
            sheet_name (str): Name of the worksheet tab.
                              If None, uses the first sheet.

        RETURNS:
            list[dict]: Each row becomes a dictionary where
                        keys are column headers and values are cell values.

        EXAMPLE:
            If your sheet looks like:
                | Name  | Description     | Category |
                | Apple | A red fruit     | Fruit    |
                | Chair | Something to    | Furniture|
                |       | sit on          |          |

            This returns:
                [
                    {"Name": "Apple", "Description": "A red fruit", "Category": "Fruit"},
                    {"Name": "Chair", "Description": "Something to sit on", "Category": "Furniture"},
                ]

        WHAT IS TYPE HINTING?
            The ": str" and "-> list[dict]" parts are type hints.
            They don't change how the code works, but they tell
            other developers (and tools) what types to expect.
        """
        # Get the right worksheet
        if sheet_name:
            worksheet = self.spreadsheet.worksheet(sheet_name)
        else:
            # get_all_worksheets() returns all tabs; [0] gets the first one
            worksheet = self.spreadsheet.worksheets()[0]

        logger.info(f"Reading data from worksheet: {worksheet.title}")

        # get_all_records() reads all rows and uses the first row as headers
        # It returns a list of dictionaries automatically
        rows = worksheet.get_all_records()

        logger.info(f"Retrieved {len(rows)} rows from the sheet")
        return rows

    def get_sheet_names(self) -> list[str]:
        """
        Returns the names of all worksheet tabs in the spreadsheet.

        RETURNS:
            list[str]: e.g., ["Sheet1", "Products", "FAQ"]
        """
        worksheets = self.spreadsheet.worksheets()
        # This is a "list comprehension" — a compact way to build a list
        # It means: for each worksheet in worksheets, get its title
        names = [ws.title for ws in worksheets]
        logger.info(f"Found sheets: {names}")
        return names

    def get_all_text(self, sheet_name: str = None, separator: str = " | ") -> list[str]:
        """
        Converts spreadsheet rows into text strings for the RAG system.

        WHY DO WE NEED THIS?
            RAG systems work with text. We need to convert the structured
            data in our spreadsheet into plain text that can be:
            1. Turned into embeddings (vectors)
            2. Retrieved when relevant to a question
            3. Shown to Claude as context

        PARAMETERS:
            sheet_name (str): Worksheet name (None = first sheet)
            separator (str): String to put between column values

        RETURNS:
            list[str]: Each row becomes one text string.

        EXAMPLE:
            Row: {"Product": "Chair", "Description": "Wooden chair", "Price": "50"}
            Text: "Product: Chair | Description: Wooden chair | Price: 50"
        """
        rows = self.get_all_rows(sheet_name)
        texts = []

        for row in rows:
            # Build a text string from all columns in this row
            # row.items() returns pairs like [("Name", "Apple"), ("Color", "Red")]
            parts = []
            for column_name, cell_value in row.items():
                # Skip empty cells to keep text clean
                if cell_value:
                    parts.append(f"{column_name}: {cell_value}")

            # Join all parts with the separator
            # "separator.join(list)" puts the separator between each item
            if parts:
                row_text = separator.join(parts)
                texts.append(row_text)

        logger.info(f"Converted {len(texts)} rows to text")
        return texts

    def get_metadata(self, sheet_name: str = None) -> list[dict]:
        """
        Gets raw row data as metadata to store alongside text chunks.

        WHAT IS METADATA?
            Metadata is "data about data." When we store a text chunk
            in our vector store, we also store metadata (the original
            row data) so we can show the source to users.

        RETURNS:
            list[dict]: The raw rows, each as a dictionary.
        """
        return self.get_all_rows(sheet_name)
