import chromadb
from chromadb.utils import embedding_functions
import logging
import argparse
from kb_chatbot.logging_config import configure_logging

logger = logging.getLogger(__name__)

class VectorDBTester:
    def __init__(self, chroma_db_path, collection_name):
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-mpnet-base-v2")
        self.chroma_client = chromadb.PersistentClient(path=chroma_db_path)
        self.collection = self.chroma_client.get_collection(name=collection_name, embedding_function=self.embedding_function)
        
        logger.info(f"Using Chroma database persisted at: {chroma_db_path}")
        logger.info(f"Using collection: {collection_name}")

    def query_database(self, query_text, n_results=3):
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        return results

    def test_inference(self, test_statement):
        logger.info(f"Testing statement: '{test_statement}'")
        
        results = self.query_database(test_statement)

        if not results['documents'] or not results['documents'][0]:
            print("No results found.")
            return

        print("Top 3 most similar entries in the database:")
        max_similarity = 0
        for i, (document, metadata, distance) in enumerate(zip(results['documents'][0], results['metadatas'][0], results['distances'][0]), 1):
            similarity = 1 / (1 + distance)
            max_similarity = max(max_similarity, similarity)

            print(f"{i}. Similarity: {similarity:.4f}")
            print(f"   Title: {metadata.get('title', 'No Title')}")
            print(f"   Content: {document[:200]}...")  # Print first 200 characters

        if max_similarity > 0.5:  # Threshold can be adjusted
            print("Analysis: The statement appears to be closely related to content in the database.")
        else:
            print("Analysis: The statement doesn't seem to closely match any content in the database.")

def perform_inference(chroma_db_path, collection_name, statement):
    tester = VectorDBTester(chroma_db_path, collection_name)
    tester.test_inference(statement)

def main():
    parser = argparse.ArgumentParser(description="Test vector database inference.")
    parser.add_argument("chroma_db_path", type=str, help="Path to the Chroma database directory")
    parser.add_argument("collection_name", type=str, help="Name of the Chroma collection to query")
    parser.add_argument("statement", type=str, help="The statement to test against the vector database.")
    parser.add_argument("--log-level", type=str, default="ERROR", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Set the logging level (default: ERROR)")
    args = parser.parse_args()

    # Configure logging using the existing function
    configure_logging(getattr(logging, args.log_level))

    perform_inference(args.chroma_db_path, args.collection_name, args.statement)

if __name__ == "__main__":
    main()
