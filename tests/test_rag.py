import pytest
from unittest.mock import patch, mock_open, MagicMock
import json
import sys
from kb_chatbot.rag import main

@pytest.fixture
def mock_openai_client():
    # Create the mock hierarchy
    mock_message = MagicMock()
    mock_message.content = "Test ChatGPT response"
    
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    
    mock_completions = MagicMock()
    mock_completions.create.return_value = mock_response
    
    mock_chat = MagicMock()
    mock_chat.completions = mock_completions
    
    mock_client = MagicMock()
    mock_client.chat = mock_chat
    
    return mock_client

@pytest.fixture
def mock_config():
    return {
        "openai_api_key": "test-key",
        "chroma_db_path": "/test/path",
        "collection_name": "test_collection"
    }

@pytest.fixture
def mock_collection():
    collection = MagicMock()
    return collection

@pytest.fixture
def mock_client(mock_collection):
    client = MagicMock()
    client.get_collection.return_value = mock_collection
    return client

def test_successful_rag(capsys, mock_config, mock_client, mock_collection, mock_openai_client):
    """Test successful RAG execution"""
    test_args = [
        'rag.py',
        '/test/path',
        'test_collection',
        'test query',
        '--config',
        'test_config.json'
    ]
    
    mock_results = {
        'documents': [['Test document content']],
        'metadatas': [[{'title': 'Test Title'}]],
        'distances': [[0.1]]
    }
    mock_collection.query.return_value = mock_results

    with patch.object(sys, 'argv', test_args), \
         patch('builtins.open', mock_open(read_data=json.dumps(mock_config))), \
         patch('chromadb.PersistentClient', return_value=mock_client), \
         patch('chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'), \
         patch('kb_chatbot.rag.OpenAI', return_value=mock_openai_client):  # Patch the actual import path
        
        main()
        
        # Verify the mock was used correctly
        mock_openai_client.chat.completions.create.assert_called_once()
        
        captured = capsys.readouterr()
        assert "Test ChatGPT response" in captured.out
