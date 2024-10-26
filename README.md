# Knowledgebase Chatbot
Use Retrieved Augmented Generation (RAG) to create a Knowledge ChatBot from information contained in just about any source (initially OneNote Notebooks supported but definitely looking forward to add handlers for all repositories out there as well as all file types). The retrieved data is given to ChatGPT in a prompt to deliver augmented generative responses. In other words to obtain human-like responses from human-like questions taking into account external to the AI knowledge. 

```
% tree --gitignore
├── LICENSE
├── MANIFEST.in
├── README.md
├── kb_chatbot
│   ├── __init__.py
│   ├── inference.py
│   ├── logging_config.py
│   ├── rag.py
│   └── sync
│       ├── __init__.py
│       └── onenote.py
├── pytest.ini
├── requirements-dev.txt
├── requirements.txt
├── setup.py
└── tests
    ├── __init__.py
    ├── test_inference.py
    ├── test_onenote_sync.py
    └── test_rag.py
```


# Prerequisites
Have a hidden .config.json with the below info:
```
{
    "client_id": "",
    "tenant_id": "",
    "client_secret": "",
    "sharepoint_domain": "",
    "chroma_db_path": "",
    "optional_log_path": "",
    "sync_state_path": "",
    "optional_downloaded_content_path": "",
    "openai_api_key": ""
}
```

# Virtual environment
Better to always use an isolated environment. To that end install and activate venv:
```
python3 -m venv venv
source venv/bin/activate
```
Once you are done deactivate so that you start clean and avoid dependency related issues:
```
deactivate
rm -rf venv
```

# Dependencies
## Initial Setup
The project's base dependencies were initially discovered using pipreqs:
```
pipreqs .
```

Note: You should not need to run this command again as dependencies are now maintained manually in dedicated files.

## Dependencies management
Dependencies are maintained in two separate files:

* requirements.txt: Production dependencies required to run the package
* requirements-dev.txt: Development dependencies (testing, formatting, linting)

These files are used by setup.py to enable flexible installation options:

### Installing from PyPI
```
# Install just production dependencies
pip install kb-chatbot

# Install both production and development dependencies
pip install kb-chatbot[dev]
```

### Installing for Local Development
```
# Install just production dependencies
pip install -r requirements.txt

# Install both production and development dependencies
pip install -r requirements-dev.txt
```

### Package Development
For developers who are working on the package itself and need to test package installation:
```
# Install in editable mode with production dependencies
pip install -e .

# Install in editable mode with both production and development dependencies
pip install -e ".[dev]"
```
The -e flag installs the package in "editable" mode, meaning changes to the source code will be reflected immediately without requiring reinstallation.

### Adding New Dependencies

1. For production dependencies: Add the package to requirements.txt
1. For development dependencies: Add the package to requirements-dev.txt


# Buiding the package
```
pip install -e .
```

# Extracting OneNote Notebook Content into a Chroma Vector Database
To extract content from a OneNote notebook and index it into a Chroma vector database, execute the following command:
```
# direct script execution
python kb_chatbot/sync/onenote.py <site_name> "<notebook_name>" --config <path to .config.json>
# package based execution)
kb-onenote-sync <site_name> "<notebook_name>" --config <path to .config.json>
```

For example:
```
# direct script execution
python kb_chatbot/sync/onenote.py MyCompany "MyCompany Notebook" --config .config.json
# package based execution)
kb-onenote-sync MyCompany "MyCompany Notebook" --config .config.json
```

# Validating the Effectiveness of Stored Embeddings
To verify whether the embeddings stored in the vector database are accurately retrieving relevant content, run the following command:
```
# direct script execution
python kb_chatbot/inference.py <chroma_db_path> <collection_name> 'Your query here'
# package based execution
kb-inference <chroma_db_path> <collection_name> 'Your query here'
```

For example:
```
# direct script execution
python kb_chatbot/inference.py /Users/nu/Downloads/mycompany_notebook_chroma_db onenote_MyCompany_MyCompanyNotebook 'What is the NAV Template and how to use it?'
# package based execution
kb-inference /Users/nu/Downloads/mycompany_notebook_chroma_db onenote_MyCompany_MyCompanyNotebook 'What is the NAV Template and how to use it?'
```

# Performing Retrieval-Augmented Generation (RAG) with ChatGPT
The vector_db_rag_chatgpt.py script allows you to generate responses using the content from your vector database as context. It retrieves the top three most relevant documents from the Chroma vector database and uses them as context to prompt the ChatGPT API. The assistant's response will be in markdown format, suitable for rendering similarly to the ChatGPT chat window. Use the below command to that end:
```
# direct script execution
python kb_chatbot/rag.py <chroma_db_path> <collection_name> 'Your query here' --config <path to .config.json>
# package based execution)
kb-rag <chroma_db_path> <collection_name> 'Your query here' --config <path to .config.json>
```

For example:
```
# direct script execution
python kb_chatbot/rag.py /Users/nu/Downloads/mycompany_notebook_chroma_db onenote_MyCompany_MyCompanyNotebook "How to book a Split in Paxus" --config .config.json
# package based execution)
kb-rag /Users/nu/Downloads/mycompany_notebook_chroma_db onenote_MyCompany_MyCompanyNotebook "How to book a Split in Paxus" --config .config.json
```

# Find content of all relevant files in a project respecting .gitignore)
```
fd -t f -0 | xargs -0 -I {} sh -c 'echo "File: {}"; cat {}' # fd better than find
```

# Linter
Code should adhere to PEP 8.
```
flake8 kb_chatbot
```

## Formatter
Use black if in need to make a file PEP 8 compatible.
```
black kb_chatbot/sync.py
```

# Tests
Use pytest to run all the package tests which are included in the tests/ dir:
```
pytest
```
