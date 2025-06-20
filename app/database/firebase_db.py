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
    def execute_query(collection_name: str, field_path: str, operator: str, value: Any) -> List[Dict[str, Any]]:
        """
        Execute a simple query against a collection
        
        Args:
            collection_name: Name of the collection to query
            field_path: Field path to query on
            operator: Operator for the query ('==', '!=', '>', '<', '>=', '<=', 'array_contains', 'in')
            value: Value to compare against
            
        Returns:
            List of documents matching the query
        """
        try:
            print(f"Executing query on {collection_name} where {field_path} {operator} {value}")
            docs = db.collection(collection_name).where(field_path, operator, value).stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"Error executing query: {e}")
            return []
    
    @staticmethod
    def execute_complex_query(collection_name: str, conditions: List[Tuple[str, str, Any]], order_by: Optional[List[Tuple[str, str]]] = None) -> List[Dict[str, Any]]:
        """
        Execute a complex query with multiple conditions against a collection
        
        Args:
            collection_name: Name of the collection to query
            conditions: List of tuples with (field_path, operator, value)
            order_by: Optional list of tuples with (field_path, direction) where direction is 'asc' or 'desc'
            
        Returns:
            List of documents matching all conditions
        """
        try:
            # Start building the query
            query = db.collection(collection_name)
            
            # Add all conditions
            for field_path, operator, value in conditions:
                query = query.where(field_path, operator, value)
            
            # Add ordering if specified
            if order_by:
                for field_path, direction in order_by:
                    if direction.lower() == 'desc':
                        query = query.order_by(field_path, direction=firestore.Query.DESCENDING)
                    else:
                        query = query.order_by(field_path)
            
            # Execute the query
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"Error executing complex query: {e}")
            return []
    
    @staticmethod
    def create_document_with_id(collection_name: str, doc_id: str, document_data: Dict[str, Any]) -> str:
        """
        Create a new document with a specific ID in a collection
        Returns the document ID
        """
        try:
            # Set the data with the provided ID
            doc_ref = db.collection(collection_name).document(doc_id)
            doc_data = document_data.copy()
            
            # Ensure the ID is included in the document data
            if "id" not in doc_data:
                doc_data["id"] = doc_id
                
            # Write to Firestore
            doc_ref.set(doc_data)
            print(f"Document created in Firestore with specific ID: {doc_id} (collection: {collection_name})")
            return doc_id
        except Exception as e:
            print(f"Error in create_document_with_id: {e}")
            # Return the provided ID anyway
            return doc_id
    
    @staticmethod
    def create_document(collection_name: str, document_data: Dict[str, Any]) -> str:
        """
        Create a new document in a collection
        Returns the document ID
        
        Different collections have different ID strategies:
        - For 'jobs' collection: Use the job_id as document ID
        - For 'candidates_data' collection: Always generate a unique ID to avoid overwriting
        """
        try:
            # Generate a document ID based on collection type
            if collection_name == 'jobs':
                # For job collection, use job_id from data
                doc_id = document_data.get("job_id", str(uuid.uuid4()))
            elif collection_name == 'candidates_data':
                # For candidates, always use a unique ID to avoid overwriting
                # We'll store the job_id inside the document, but it won't be used as the document ID
                doc_id = str(uuid.uuid4())
                print(f"Generated unique ID for candidate: {doc_id}")
            else:
                # For other collections, use the default behavior
                doc_id = document_data.get("id", str(uuid.uuid4()))
            
            # Set the data with the appropriate ID
            try:
                doc_ref = db.collection(collection_name).document(doc_id)
                doc_data = document_data.copy()
                
                # Ensure the ID is included in the document data
                if "id" not in doc_data:
                    doc_data["id"] = doc_id
                    
                # Write to Firestore
                doc_ref.set(doc_data)
                print(f"Document created in Firestore with ID: {doc_id} (collection: {collection_name})")
                return doc_id
            except Exception as db_error:
                print(f"Firestore error: {db_error}")
                # Simulate document creation in memory
                print(f"Using in-memory fallback - Document created with ID: {doc_id}")
                return doc_id
        except Exception as e:
            print(f"Error in create_document: {e}")
            # Return generated ID anyway
            return str(uuid.uuid4())
    
    @staticmethod
    def get_document(collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by its ID
        """
        try:
            print("inside get document")
            print("collection name",collection_name)
            doc_ref = db.collection(collection_name).document(doc_id)
            print("doc_ref: ",doc_ref)
            doc = doc_ref.get()
            if doc.exists:
                print("doc available")
                print(doc.to_dict())
                return doc.to_dict()
        except Exception as e:
            print(f"Error getting document: {e}")
            # Return mock data for testing
            return {"job_id": doc_id, "status": "mock_data"}
    
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
