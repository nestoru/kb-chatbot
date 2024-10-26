# tests/test_inference.py
import pytest
from unittest.mock import patch, MagicMock
import logging
import sys
from kb_chatbot.inference import main

@pytest.fixture
def mock_collection():
    collection = MagicMock()
    return collection

@pytest.fixture
def mock_client(mock_collection):
    client = MagicMock()
    client.get_collection.return_value = mock_collection
    return client

def test_successful_query(capsys, mock_client, mock_collection):
    """Test successful query execution"""
    test_args = ['inference.py', '/test/path', 'test_collection', 'test query']
    
    mock_results = {
        'documents': [['Document content 1']],
        'metadatas': [[{'title': 'Test Title'}]],
        'distances': [[0.1]]
    }
    mock_collection.query.return_value = mock_results

    with patch.object(sys, 'argv', test_args), \
         patch('chromadb.PersistentClient', return_value=mock_client), \
         patch('chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):
        
        main()
        
        captured = capsys.readouterr()
        assert "Top 3 most similar entries in the database:" in captured.out
        assert "Document content 1" in captured.out
        assert "Test Title" in captured.out

def test_empty_results(capsys, mock_client, mock_collection):
    """Test behavior with empty results"""
    test_args = ['inference.py', '/test/path', 'test_collection', 'test query']
    
    mock_results = {
        'documents': [[]],
        'metadatas': [[]],
        'distances': [[]]
    }
    mock_collection.query.return_value = mock_results

    with patch.object(sys, 'argv', test_args), \
         patch('chromadb.PersistentClient', return_value=mock_client), \
         patch('chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction'):
        
        main()
        
        captured = capsys.readouterr()
        assert "No results found" in captured.out

def test_invalid_arguments():
    """Test behavior with missing arguments"""
    test_args = ['inference.py']
    
    with patch.object(sys, 'argv', test_args), \
         pytest.raises(SystemExit) as exc_info:
        main()
    
    assert exc_info.value.code != 0

