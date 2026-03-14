import os
import io
import logging

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]

MIME_PDF    = "application/pdf"
MIME_GDOC   = "application/vnd.google-apps.document"
MIME_GSHEET = "application/vnd.google-apps.spreadsheet"
MIME_FOLDER = "application/vnd.google-apps.folder"


class GoogleDriveConnector:
    """
    Reads PDFs and Google Docs from Google Drive and returns their text.

    USAGE:
        drive = GoogleDriveConnector()
        docs  = drive.list_files()          # list all readable files
        texts = drive.get_all_texts()       # extract text from all files
    """

    def __init__(self):
        self.credentials_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        self.folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
        self.service = self._build_service()

    def _build_service(self):
        creds = Credentials.from_service_account_file(self.credentials_path, scopes=SCOPES)
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        logger.info("Google Drive service initialised")
        return service

    # ── File listing ─────────────────────────────────────────────────────────

    def list_files(self) -> list[dict]:
        """
        Return all PDFs and Google Docs the service account can access.
        If GOOGLE_DRIVE_FOLDER_ID is set in .env, only files inside that
        folder are returned.
        """
        mime_filter = " or ".join([
            f"mimeType='{MIME_PDF}'",
            f"mimeType='{MIME_GDOC}'",
        ])
        query = f"({mime_filter}) and trashed=false"

        if self.folder_id:
            query += f" and '{self.folder_id}' in parents"

        files = []
        page_token = None
        while True:
            resp = self.service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
                pageToken=page_token,
                pageSize=100,
            ).execute()
            files.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        logger.info(f"Found {len(files)} Drive files (PDFs + Docs)")
        return files

    # ── Text extraction ───────────────────────────────────────────────────────

    def get_text_from_file(self, file: dict) -> str:
        """Extract text from a single file dict returned by list_files()."""
        mime = file["mimeType"]
        name = file["name"]
        fid  = file["id"]

        try:
            if mime == MIME_GDOC:
                return self._export_gdoc(fid, name)
            elif mime == MIME_PDF:
                return self._download_pdf(fid, name)
            else:
                logger.warning(f"Unsupported mime type '{mime}' for '{name}'")
                return ""
        except Exception as e:
            logger.error(f"Failed to extract text from '{name}': {e}")
            return ""

    def _export_gdoc(self, file_id: str, name: str) -> str:
        """Export a Google Doc as plain text."""
        logger.info(f"Exporting Google Doc: {name}")
        resp = self.service.files().export(
            fileId=file_id,
            mimeType="text/plain"
        ).execute()
        text = resp.decode("utf-8") if isinstance(resp, bytes) else resp
        logger.info(f"Extracted {len(text)} chars from Doc '{name}'")
        return text

    def _download_pdf(self, file_id: str, name: str) -> str:
        """Download a PDF and extract its text using pypdf."""
        from pypdf import PdfReader

        logger.info(f"Downloading PDF: {name}")
        request = self.service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        buf.seek(0)
        reader = PdfReader(buf)
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages)
        logger.info(f"Extracted {len(text)} chars from PDF '{name}' ({len(reader.pages)} pages)")
        return text

    # ── Bulk helpers for RAG pipeline ─────────────────────────────────────────

    def get_all_texts(self) -> list[str]:
        """Return extracted text for every readable Drive file."""
        files = self.list_files()
        texts = []
        for f in files:
            text = self.get_text_from_file(f)
            if text.strip():
                texts.append(text)
        return texts

    def get_all_texts_with_metadata(self) -> list[tuple[str, dict]]:
        """
        Return (text, metadata) pairs for every readable Drive file.
        metadata contains file name, id, mimeType, modifiedTime.
        """
        files = self.list_files()
        results = []
        for f in files:
            text = self.get_text_from_file(f)
            if text.strip():
                meta = {
                    "_source":       "google_drive",
                    "_file_name":    f["name"],
                    "_file_id":      f["id"],
                    "_mime_type":    f["mimeType"],
                    "_modified_time": f.get("modifiedTime", ""),
                }
                results.append((text, meta))
        return results
