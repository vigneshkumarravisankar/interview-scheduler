"""
Firebase database wrapper with MockDB fallback for testing and development
"""

from typing import Dict, Any, Optional, List, Tuple
import os
import time
import uuid
import logging
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK if not already initialized
if not firebase_admin._apps:
    cred_path = os.environ.get("FIREBASE_CREDENTIALS") or os.path.join(os.path.dirname(__file__), "../config/service_account.json")
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
db = firestore.client()

class FirestoreDB:
    """
    Wrapper for Firestore operations using Firebase Firestore
    """

    @staticmethod
    def get_server_timestamp():
        """Return a server timestamp (Firestore server timestamp)"""
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP
        return SERVER_TIMESTAMP

    @staticmethod
    def collection_exists(collection_name: str) -> bool:
        """Check if a collection exists (by checking if it has any documents)"""
        docs = db.collection(collection_name).limit(1).get()
        return len(docs) > 0

    @staticmethod
    def add_document(collection_name: str, document_data: Dict[str, Any], doc_id: Optional[str] = None) -> str:
        """Add a document to a collection, optionally with a specific ID"""
        col_ref = db.collection(collection_name)
        if doc_id:
            document_data["id"] = doc_id
            col_ref.document(doc_id).set(document_data)
            return doc_id
        else:
            doc_ref = col_ref.document()
            document_data["id"] = doc_ref.id
            doc_ref.set(document_data)
            return doc_ref.id

    @staticmethod
    def get_document(collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by its ID"""
        doc = db.collection(collection_name).document(doc_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    @staticmethod
    def get_all_documents(collection_name: str) -> List[Dict[str, Any]]:
        """Get all documents in a collection"""
        docs = db.collection(collection_name).stream()
        return [doc.to_dict() for doc in docs]

    @staticmethod
    def update_document(collection_name: str, doc_id: str, data: Dict[str, Any]) -> None:
        """Update a document"""
        db.collection(collection_name).document(doc_id).update(data)

    @staticmethod
    def delete_document(collection_name: str, doc_id: str) -> None:
        """Delete a document"""
        db.collection(collection_name).document(doc_id).delete()

    @staticmethod
    def execute_query(collection_name: str, field_path: str, operator: str, value: Any) -> List[Dict[str, Any]]:
        """Execute a simple query against a collection"""
        col_ref = db.collection(collection_name)
        query = col_ref.where(field_path, operator, value)
        docs = query.stream()
        return [doc.to_dict() for doc in docs]

    @staticmethod
    def create_document(collection_name: str, document_data: Dict[str, Any]) -> str:
        """Create a new document (legacy method, use add_document instead)"""
        # Generate a document ID based on collection type
        if collection_name == "jobs":
            doc_id = document_data.get("job_id", str(uuid.uuid4()))
        elif collection_name == "candidates_data":
            doc_id = str(uuid.uuid4())
        else:
            doc_id = document_data.get("id", str(uuid.uuid4()))

        # Ensure the ID is included in the document data
        doc_data = document_data.copy()
        if "id" not in doc_data:
            doc_data["id"] = doc_id

        # Call the new add_document method
        return FirestoreDB.add_document(collection_name, doc_data, doc_id)
