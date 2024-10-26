import sys
import json
import os
import logging
import argparse
from openai import OpenAI
import chromadb
from chromadb.utils import embedding_functions
from kb_chatbot.logging_config import configure_logging

# Suppress tokenizer parallelism warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Get a logger for this module
logger = logging.getLogger(__name__)

class VectorDBRAGChatGPT:
    def __init__(self, chroma_db_path, collection_name, config_path):
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-mpnet-base-v2"
        )

        try:
            self.chroma_client = chromadb.PersistentClient(path=chroma_db_path)
            logger.debug(f"Connected to ChromaDB at {chroma_db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB at {chroma_db_path}: {e}")
            sys.exit(1)

        try:
            self.collection = self.chroma_client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            logger.debug(f"Accessing ChromaDB collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to get ChromaDB collection '{collection_name}': {e}")
            sys.exit(1)

        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            logger.debug(f"Loaded configuration from {config_path}")
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_path}")
            sys.exit(1)
        except json.JSONDecodeError:
            logger.error(f"Configuration file is not valid JSON: {config_path}")
            sys.exit(1)

        self.openai_api_key = self.config.get('openai_api_key')
        if not self.openai_api_key:
            logger.error("OpenAI API key not found in config.json")
            print('ERROR: OpenAI API key not found in config.json.')
            sys.exit(1)

        self.client = OpenAI(api_key=self.openai_api_key)
        logger.debug("Initialized OpenAI API client")

    def query_database(self, query_text, n_results=3):
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            return results
        except Exception as e:
            logger.error(f"Error querying the database: {e}")
            return None

    def perform_rag(self, question):
        results = self.query_database(question)

        if not results or not results.get('documents') or not results['documents'][0]:
            logger.warning("No results found in the vector database for the given query.")
            print("No relevant information found in the database to answer your question.")
            return

        context_documents = results['documents'][0]
        context = "\n\n".join(context_documents)

        messages = []
        if self.config.get('session_prompt'):
            session_prompt = self.config.get('session_prompt')
            messages.append({"role": "system", "content": session_prompt})

        messages.append({
            "role": "system",
            "content": "You are a helpful assistant. Please provide all responses in markdown format."
        })
        messages.append({
            "role": "system",
            "content": f"Use the following context to answer the user's question. "
                       f"If the context does not provide enough information, please say so.\n\nContext:\n{context}"
        })
        messages.append({"role": "user", "content": question})

        try:
            response = self.call_chatgpt_api(messages)
            print(response)
        except Exception as e:
            logger.error(f"Error during RAG operation: {e}")
            print("An error occurred while processing your request. Please try again later.")

    def call_chatgpt_api(self, messages):
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error calling ChatGPT API: {e}")
            raise e

def perform_rag(chroma_db_path, collection_name, statement, config_path):
    rag_chatgpt = VectorDBRAGChatGPT(chroma_db_path, collection_name, config_path)
    rag_chatgpt.perform_rag(statement)

def main():
    parser = argparse.ArgumentParser(
        description="Perform Retrieval-Augmented Generation using ChromaDB and ChatGPT."
    )
    parser.add_argument("chroma_db_path", type=str, help="Path to the Chroma vector database directory.")
    parser.add_argument("collection_name", type=str, help="Name of the Chroma collection to query.")
    parser.add_argument("statement", type=str, help="The statement or question to test against the vector database.")
    parser.add_argument("--config", default=".config.json", help="Path to the configuration file.")
    parser.add_argument("--log-level", type=str, default="ERROR", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Set the logging level (default: ERROR)")
    args = parser.parse_args()

    configure_logging(getattr(logging, args.log_level))
    perform_rag(args.chroma_db_path, args.collection_name, args.statement, args.config)

if __name__ == "__main__":
    main()
