# tests/test_onenote_sync.py
import pytest
from unittest.mock import patch, MagicMock, mock_open
import json
import requests
from kb_chatbot.sync.onenote import OneNoteVectorDBSync
import tempfile
import shutil
import os

class MockResponse:
    def __init__(self, data, is_json=True):
        self._data = data
        self._is_json = is_json
        
    def json(self):
        if not self._is_json:
            raise ValueError("Not JSON")
        return self._data
        
    @property
    def text(self):
        if not isinstance(self._data, str):
            return json.dumps(self._data)
        return self._data
    
    def raise_for_status(self):
        pass

def create_mock_response(data, is_json=True):
    return MockResponse(data, is_json)

@pytest.fixture
def mock_config():
    temp_dir = tempfile.mkdtemp()
    config = {
        "client_id": "test_client_id",
        "tenant_id": "test_tenant_id",
        "client_secret": "test_client_secret",
        "sharepoint_domain": "test.sharepoint.com",
        "sync_state_path": os.path.join(temp_dir, "sync_state"),
        "chroma_db_path": os.path.join(temp_dir, "chroma_db"),
        "optional_log_path": os.path.join(temp_dir, "logs"),
        "optional_downloaded_content_path": os.path.join(temp_dir, "downloaded_content")
    }
    yield config
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_msal():
    instance = MagicMock()
    instance.acquire_token_silent.return_value = None
    instance.acquire_token_for_client.return_value = {
        "access_token": "test_token",
        "expires_in": 3600
    }
    return instance

def test_successful_sync(mock_config, mock_msal):
    """Test successful notebook synchronization"""
    mock_collection = MagicMock()
    mock_collection.add = MagicMock()
    mock_collection.delete = MagicMock()
    
    mock_chroma_client = MagicMock()
    mock_chroma_client.get_or_create_collection.return_value = mock_collection

    with patch('builtins.open', mock_open(read_data=json.dumps(mock_config))), \
         patch('os.path.isdir', return_value=True), \
         patch('requests.get') as mock_get, \
         patch('chromadb.PersistentClient', return_value=mock_chroma_client), \
         patch('msal.ConfidentialClientApplication', return_value=mock_msal), \
         patch('bs4.BeautifulSoup') as mock_bs, \
         patch('chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):
        
        mock_pages = [{
            "id": "test_page_id",
            "title": "test_page",
            "lastModifiedDateTime": "2024-03-21T14:30:00Z"
        }]

        def mock_get_side_effect(*args, **kwargs):
            url = args[0]
            if '/sites/' in url and not '/onenote/' in url:
                return create_mock_response({"id": "test_site_id"})
            elif '/notebooks' in url:
                return create_mock_response({
                    "value": [{
                        "id": "test_notebook_id",
                        "displayName": "test_notebook"
                    }]
                })
            elif '/sections/' in url and not '/pages' in url:
                return create_mock_response({
                    "value": [{
                        "id": "test_section_id",
                        "displayName": "test_section"
                    }]
                })
            elif '/sectionGroups' in url:
                return create_mock_response({"value": []})
            elif '/pages/' in url and 'content' in url:
                return create_mock_response("<html><body>Test content</body></html>", is_json=False)
            elif '/pages' in url:
                return create_mock_response({"value": mock_pages})
            return create_mock_response({"value": []})

        mock_get.side_effect = mock_get_side_effect

        # Mock BeautifulSoup text extraction
        mock_soup = MagicMock()
        mock_soup.get_text.return_value = "Test content"
        mock_soup.find_all.return_value = []  # No images
        mock_bs.return_value = mock_soup

        syncer = OneNoteVectorDBSync('test_config.json', 'test_site', 'test_notebook')
        syncer.sync()

        # Verify API calls were made
        api_calls = [call[0][0] for call in mock_get.call_args_list]
        assert any('/notebooks' in url for url in api_calls)
        assert any('/sections' in url for url in api_calls)
        assert any('/pages' in url for url in api_calls)
        assert mock_collection.add.call_count > 0

def test_sync_with_api_error(mock_config, mock_msal, capsys):
    """Test handling of API errors during sync"""
    mock_collection = MagicMock()
    mock_collection.add = MagicMock()
    
    mock_chroma_client = MagicMock()
    mock_chroma_client.get_or_create_collection.return_value = mock_collection

    with patch('builtins.open', mock_open(read_data=json.dumps(mock_config))), \
         patch('os.path.isdir', return_value=True), \
         patch('requests.get') as mock_get, \
         patch('chromadb.PersistentClient', return_value=mock_chroma_client), \
         patch('msal.ConfidentialClientApplication', return_value=mock_msal), \
         patch('chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):

        def mock_get_side_effect(*args, **kwargs):
            url = args[0]
            if '/sites/' in url and not '/onenote/' in url:
                return create_mock_response({"id": "test_site_id"})
            raise requests.exceptions.RequestException("API Error")

        mock_get.side_effect = mock_get_side_effect

        syncer = OneNoteVectorDBSync('test_config.json', 'test_site', 'test_notebook')
        syncer.run()

        # Capture the stderr output
        captured = capsys.readouterr()
        assert "API Error" in captured.err

def test_invalid_config():
    """Test behavior with invalid configuration"""
    invalid_config = {}  # Missing required fields
    
    with patch('builtins.open', mock_open(read_data=json.dumps(invalid_config))), \
         pytest.raises(SystemExit) as exc_info:
        OneNoteVectorDBSync('test_config.json', 'test_site', 'test_notebook')
    
    assert exc_info.value.code != 0

def test_notebook_not_found(mock_config, mock_msal):
    """Test behavior when notebook is not found"""
    mock_chroma_client = MagicMock()
    
    with patch('builtins.open', mock_open(read_data=json.dumps(mock_config))), \
         patch('os.path.isdir', return_value=True), \
         patch('requests.get') as mock_get, \
         patch('chromadb.PersistentClient', return_value=mock_chroma_client), \
         patch('msal.ConfidentialClientApplication', return_value=mock_msal), \
         patch('chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):

        def mock_get_side_effect(*args, **kwargs):
            url = args[0]
            if '/sites/' in url and not '/onenote/' in url:
                return create_mock_response({"id": "test_site_id"})
            elif '/notebooks' in url:
                return create_mock_response({"value": []})
            return create_mock_response({"value": []})

        mock_get.side_effect = mock_get_side_effect

        syncer = OneNoteVectorDBSync('test_config.json', 'test_site', 'test_notebook')
        with pytest.raises(ValueError) as exc_info:
            syncer.sync()
        
        assert "Notebook 'test_notebook' not found" in str(exc_info.value)

