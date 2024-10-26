# File: kb_chatbot/sync.py

import json
import hashlib
from datetime import datetime, timedelta, timezone
import requests
import msal
import chromadb
from chromadb.utils import embedding_functions
import argparse
import logging
import re
import os
import sys
from dateutil import parser
from bs4 import BeautifulSoup
import pytesseract
from PIL import Image
from io import BytesIO
from requests.exceptions import HTTPError


class OneNoteVectorDBSync:
    def __init__(self, config_path, site_name, notebook_name):
        with open(config_path, "r") as config_file:
            self.config = json.load(config_file)

        self.site_name = site_name
        self.notebook_name = notebook_name
        self.access_token = None
        self.token_expires_at = datetime.now(timezone.utc)

        # Initialize counter for pages with changes
        self.pages_with_changes = 0

        # Check for required sync_state_path
        if "sync_state_path" not in self.config or not self.config["sync_state_path"]:
            logging.error(
                "Error: 'sync_state_path' must be defined in the config file."
            )
            sys.exit(1)

        if not os.path.isdir(self.config["sync_state_path"]):
            logging.error(
                f"Error: The specified 'sync_state_path' does not exist or is not a directory: {self.config['sync_state_path']}"
            )
            sys.exit(1)

        self.setup_logging()
        self.setup_msal()
        self.site_id = self.get_site_id()
        self.setup_chroma()
        self.load_sync_state()

    def setup_logging(self):
        log_format = "%(asctime)s - %(levelname)s - %(message)s"
        logger = logging.getLogger("")
        logger.setLevel(logging.INFO)

        # Remove any existing handlers
        logger.handlers = []

        # Set up console logging
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(console_handler)

        # Set up file logging if path is provided in config
        optional_log_path = self.config.get("optional_log_path")
        if optional_log_path:
            log_file = os.path.join(
                optional_log_path,
                f'{self.site_name}_{self.notebook_name.replace(" ", "_")}_sync.log',
            )
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(logging.Formatter(log_format))
            logger.addHandler(file_handler)
            logging.info(f"Logging to file: {log_file}")
        else:
            logging.info("File logging is disabled.")

    def setup_msal(self):
        self.app = msal.ConfidentialClientApplication(
            self.config["client_id"],
            authority=f"https://login.microsoftonline.com/{self.config['tenant_id']}",
            client_credential=self.config["client_secret"],
        )

    def create_valid_collection_name(self, name):
        valid_name = re.sub(r"[^a-zA-Z0-9_-]", "", name)
        valid_name = re.sub(r"^[^a-zA-Z0-9]+", "", valid_name)
        if len(valid_name) < 3:
            valid_name = valid_name.ljust(3, "x")
        elif len(valid_name) > 63:
            valid_name = valid_name[:63]
        valid_name = re.sub(r"[^a-zA-Z0-9]+$", "", valid_name)
        return valid_name

    def setup_chroma(self):
        local_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-mpnet-base-v2"
        )
        persist_directory = self.config["chroma_db_path"]
        self.chroma_client = chromadb.PersistentClient(path=persist_directory)
        collection_name = self.create_valid_collection_name(
            f"onenote_{self.site_name}_{self.notebook_name}"
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name, embedding_function=local_ef
        )
        logging.info(f"Using Chroma collection name: {collection_name}")
        logging.info(f"Chroma database persisted at: {persist_directory}")

    def load_sync_state(self):
        file_path = os.path.join(
            self.config["sync_state_path"],
            f'sync_state_{self.site_name}_{self.notebook_name.replace(" ", "_")}.json',
        )

        try:
            with open(file_path, "r") as f:
                self.sync_state = json.load(f)
            logging.info(f"Loaded sync state from: {file_path}")
        except FileNotFoundError:
            self.sync_state = {}
            logging.info(f"No existing sync state found. Starting fresh.")

    def save_sync_state(self):
        file_path = os.path.join(
            self.config["sync_state_path"],
            f'sync_state_{self.site_name}_{self.notebook_name.replace(" ", "_")}.json',
        )

        with open(file_path, "w") as f:
            json.dump(self.sync_state, f)
        logging.info(f"Saved sync state to: {file_path}")

    def get_access_token(self):
        if self.access_token and datetime.now(timezone.utc) < self.token_expires_at:
            return self.access_token

        result = self.app.acquire_token_silent(
            ["https://graph.microsoft.com/.default"], account=None
        )
        if not result:
            logging.info("No token found in cache, attempting to get a new one...")
            result = self.app.acquire_token_for_client(
                scopes=["https://graph.microsoft.com/.default"]
            )

        if "access_token" in result:
            self.access_token = result["access_token"]
            expires_in = result.get(
                "expires_in", 3600
            )  # Default to 1 hour if not provided
            self.token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=expires_in
            )
            return self.access_token
        else:
            error_description = result.get(
                "error_description", "No error description available"
            )
            logging.error(f"Failed to acquire token. Error: {result.get('error')}")
            logging.error(f"Error description: {error_description}")
            raise Exception(f"Authentication failed: {error_description}")

    def get_site_id(self):
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        site_url = f"https://graph.microsoft.com/v1.0/sites/{self.config['sharepoint_domain']}:/sites/{self.site_name}"
        response = requests.get(site_url, headers=headers)
        response.raise_for_status()
        return response.json()["id"]

    def get_notebook(self):
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        notebooks_url = (
            f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/onenote/notebooks"
        )
        response = requests.get(notebooks_url, headers=headers)
        response.raise_for_status()
        notebooks = response.json()["value"]
        matching_notebooks = [
            nb for nb in notebooks if nb["displayName"] == self.notebook_name
        ]
        if not matching_notebooks:
            raise ValueError(
                f"Notebook '{self.notebook_name}' not found in site '{self.site_name}'"
            )
        return matching_notebooks[0]

    def get_notebook_sections(self, notebook_id):
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        sections_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/onenote/notebooks/{notebook_id}/sections"
        response = requests.get(sections_url, headers=headers)
        response.raise_for_status()
        return response.json()["value"]

    def get_notebook_section_groups(self, notebook_id):
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        section_groups_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/onenote/notebooks/{notebook_id}/sectionGroups"
        response = requests.get(section_groups_url, headers=headers)
        response.raise_for_status()
        return response.json()["value"]

    def get_section_group_sections(self, section_group_id):
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        sections_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/onenote/sectionGroups/{section_group_id}/sections"
        response = requests.get(sections_url, headers=headers)
        response.raise_for_status()
        return response.json()["value"]

    def get_section_group_section_groups(self, section_group_id):
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        section_groups_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/onenote/sectionGroups/{section_group_id}/sectionGroups"
        response = requests.get(section_groups_url, headers=headers)
        response.raise_for_status()
        return response.json()["value"]

    def get_section_pages(self, section_id):
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        pages_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/onenote/sections/{section_id}/pages"
        response = requests.get(pages_url, headers=headers)
        response.raise_for_status()
        return response.json()["value"]

    def get_page_content(self, page_id):
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        content_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/onenote/pages/{page_id}/content"
        response = requests.get(content_url, headers=headers)
        response.raise_for_status()
        return response.text  # Return HTML content as string

    def save_downloaded_content(
        self, full_section_name, page_title, page_id, content, extension
    ):
        content_path = self.config["optional_downloaded_content_path"]
        if not os.path.exists(content_path):
            os.makedirs(content_path)

        # Create a valid filename from full section name and page title
        valid_filename = re.sub(
            r"[^\w\-_\. ]", "_", f"{full_section_name}_{page_title}"
        )
        valid_filename = valid_filename.replace(" ", "_")
        file_path = os.path.join(content_path, f"{valid_filename}.{extension}")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logging.info(f"Saved downloaded content for page '{page_title}' to {file_path}")
        return file_path  # Return the path to the saved file

    def extract_text_from_html(self, html_content):
        soup = BeautifulSoup(html_content, "html.parser")

        # Extract text content
        text = soup.get_text(separator="\n")

        # Find all images and perform OCR
        images = soup.find_all("img")
        for img in images:
            img_src = img.get("data-fullres-src") or img.get("src")
            if img_src:
                # Some image URLs are relative; construct the full URL if necessary
                if img_src.startswith("http"):
                    img_url = img_src
                else:
                    img_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/onenote/resources/{img_src}/content"
                try:
                    img_data = self.download_image(img_url)
                    img_text = self.perform_ocr(img_data)
                    text += "\n" + img_text
                except Exception as e:
                    logging.error(f"Error processing image at {img_url}: {str(e)}")
        return text

    def download_image(self, img_url):
        headers = {"Authorization": f"Bearer {self.get_access_token()}"}
        response = requests.get(img_url, headers=headers)
        response.raise_for_status()
        return response.content

    def perform_ocr(self, img_data):
        image = Image.open(BytesIO(img_data))
        text = pytesseract.image_to_string(image)
        return text

    def hash_content(self, content):
        return hashlib.md5(content.encode()).hexdigest()

    def update_vector_db(self, page_id, title, text_content):
        # Split text into paragraphs
        paragraphs = text_content.split("\n\n")
        for i, paragraph in enumerate(paragraphs):
            if paragraph.strip():  # Skip empty paragraphs
                doc_id = f"{page_id}_{i}"
                self.collection.delete(ids=[doc_id])
                self.collection.add(
                    documents=[paragraph.strip()],
                    metadatas=[{"title": title}],
                    ids=[doc_id],
                )

    def parse_date(self, date_string):
        try:
            dt = parser.isoparse(date_string)
            if dt.tzinfo is None:
                # Assume UTC if no timezone info
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            raise ValueError(f"Unable to parse date string: {date_string}")

    def sync(self):
        try:
            notebook = self.get_notebook()
            self.sync_notebook(notebook)
            self.save_sync_state()
        except Exception as e:
            logging.error(f"Error syncing notebook: {str(e)}")
            logging.error(f"Sync failed: {str(e)}")
            raise

    def sync_notebook(self, notebook):
        notebook_id = notebook["id"]
        logging.info(f"Syncing notebook: {self.notebook_name}")

        try:
            # Sync top-level sections
            sections = self.get_notebook_sections(notebook_id)
            logging.info(
                f"Found {len(sections)} sections in notebook '{self.notebook_name}'"
            )
            for section in sections:
                self.sync_section([], section)

            # Sync top-level section groups
            section_groups = self.get_notebook_section_groups(notebook_id)
            logging.info(
                f"Found {len(section_groups)} section groups in notebook '{self.notebook_name}'"
            )
            for section_group in section_groups:
                self.sync_section_group([], section_group)

        except HTTPError as e:
            logging.error(f"Error syncing notebook '{self.notebook_name}': {str(e)}")

    def sync_section_group(self, parent_names, section_group):
        section_group_id = section_group["id"]
        section_group_name = section_group["displayName"]
        logging.info(
            f"Syncing section group: {'/'.join(parent_names + [section_group_name])}"
        )

        # Sync sections in this section group
        sections = self.get_section_group_sections(section_group_id)
        for section in sections:
            self.sync_section(parent_names + [section_group_name], section)

        # Recursively sync nested section groups
        nested_section_groups = self.get_section_group_section_groups(section_group_id)
        for nested_section_group in nested_section_groups:
            self.sync_section_group(
                parent_names + [section_group_name], nested_section_group
            )

    def sync_section(self, parent_names, section):
        section_id = section["id"]
        section_name = section["displayName"]
        full_section_name = "_".join(parent_names + [section_name])
        logging.info(f"Syncing section: {full_section_name}")

        try:
            pages = self.get_section_pages(section_id)
            logging.info(f"Found {len(pages)} pages in section '{full_section_name}'")
            for page in pages:
                self.sync_page(full_section_name, page)
        except HTTPError as e:
            logging.error(f"Error syncing section '{full_section_name}': {str(e)}")

    def sync_page(self, full_section_name, page):
        page_id = page["id"]
        page_title = page["title"]
        last_modified = self.parse_date(page["lastModifiedDateTime"])

        if page_id in self.sync_state:
            stored_last_modified = self.parse_date(
                self.sync_state[page_id]["last_modified"]
            )
            if last_modified <= stored_last_modified:
                logging.info(f"Page '{page_title}' is up to date. Skipping.")
                return

        try:
            html_content = self.get_page_content(page_id)
            content_hash = self.hash_content(html_content)

            if (
                page_id not in self.sync_state
                or content_hash != self.sync_state[page_id]["hash"]
            ):
                # Extract text from HTML and images
                text_content = self.extract_text_from_html(html_content)

                # Update vector database
                self.update_vector_db(page_id, page_title, text_content)

                self.sync_state[page_id] = {
                    "hash": content_hash,
                    "last_modified": last_modified.isoformat(),
                }

                if "optional_downloaded_content_path" in self.config:
                    # Save HTML file
                    html_file_path = self.save_downloaded_content(
                        full_section_name, page_title, page_id, html_content, "html"
                    )
                    # Optionally save extracted text
                    txt_file_path = html_file_path.replace(".html", ".txt")
                    with open(txt_file_path, "w", encoding="utf-8") as f:
                        f.write(text_content)
                    logging.info(
                        f"Saved extracted text for page '{page_title}' to {txt_file_path}"
                    )

                logging.info(f"Successfully synced page: {page_title}")

                # Increment the counter for pages with changes
                self.pages_with_changes += 1
            else:
                logging.info(
                    f"Content unchanged for page: {page_title}. Skipping update."
                )
        except HTTPError as e:
            logging.error(f"Error syncing page '{page_title}': {str(e)}")

    def run(self):
        logging.info(
            f"Starting sync for notebook '{self.notebook_name}' in site '{self.site_name}'"
        )

        # Record the start time
        start_time = datetime.now(timezone.utc)

        try:
            self.sync()
            elapsed_time = datetime.now(timezone.utc) - start_time
            logging.info(
                f"Sync completed for notebook '{self.notebook_name}' in site '{self.site_name}'"
            )
            logging.info(f"Total time taken: {elapsed_time}")
            logging.info(f"Number of pages with changes: {self.pages_with_changes}")
        except Exception as e:
            logging.error(f"Sync failed: {str(e)}")
            logging.error(f"Error: {str(e)}")


def sync_notebook(config_path, site_name, notebook_name):
    """
    Sync a OneNote notebook to a vector database.

    Args:
    config_path (str): Path to the configuration file.
    site_name (str): Name of the SharePoint site.
    notebook_name (str): Name of the OneNote notebook.

    Returns:
    None
    """
    syncer = OneNoteVectorDBSync(config_path, site_name, notebook_name)
    syncer.run()


def main():
    parser = argparse.ArgumentParser(
        description="Sync OneNote notebook from SharePoint to Vector DB."
    )
    parser.add_argument("site_name", help="Name of the SharePoint site")
    parser.add_argument("notebook_name", help="Name of the OneNote notebook")
    parser.add_argument(
        "--config", default="config.json", help="Path to the configuration file"
    )

    args = parser.parse_args()

    sync_notebook(args.config, args.site_name, args.notebook_name)


if __name__ == "__main__":
    main()
