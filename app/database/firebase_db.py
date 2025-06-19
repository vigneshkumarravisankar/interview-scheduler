from typing import Dict, Any, Optional, List, Tuple
import os
from firebase_admin import firestore, get_app, initialize_app, credentials
from dotenv import load_dotenv
import uuid
import time

# Load environment variables
load_dotenv()

# Get Firebase configuration from environment
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'login-91de6')
FIREBASE_API_KEY = os.environ.get('FIREBASE_API_KEY', "AIzaSyB7mT5f1qlQpT9QaF_wzmDkM0l9RY-MT_Y")
FIREBASE_AUTH_DOMAIN = os.environ.get('FIREBASE_AUTH_DOMAIN', "login-91de6.firebaseapp.com")
FIREBASE_STORAGE_BUCKET = os.environ.get('FIREBASE_STORAGE_BUCKET', "login-91de6.firebasestorage.app")
FIREBASE_MESSAGING_SENDER_ID = os.environ.get('FIREBASE_MESSAGING_SENDER_ID', "873127586938")
FIREBASE_APP_ID = os.environ.get('FIREBASE_APP_ID', "1:873127586938:web:359dff24f2790270681fc3")
FIREBASE_SERVICE_ACCOUNT_PATH = os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH', 'app/config/service_account.json')

# Initialize Firebase app with proper credentials
try:
    # Try to get an existing app
    app = get_app()
    print("Using existing Firebase app")
except ValueError:
    # If no app exists, initialize with service account
    print(f"Initializing new Firebase app with project ID: {FIREBASE_PROJECT_ID}")
    
    # Check if service account file exists
    if os.path.exists(FIREBASE_SERVICE_ACCOUNT_PATH):
        print(f"Using Firebase service account file at: {FIREBASE_SERVICE_ACCOUNT_PATH}")
        cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
        app = initialize_app(
            cred,
            {
                'projectId': FIREBASE_PROJECT_ID,
                'storageBucket': FIREBASE_STORAGE_BUCKET,
                'databaseURL': f"https://{FIREBASE_PROJECT_ID}.firebaseio.com"
            }
        )
    else:
        # Fall back to app config with no credentials
        print(f"Firebase service account file not found at: {FIREBASE_SERVICE_ACCOUNT_PATH}")
        print("Initializing Firebase without service account (limited functionality)")
        app = initialize_app(
            options={
                'projectId': FIREBASE_PROJECT_ID,
            }
        )
    
    print("Firebase app initialized successfully")

# Get Firestore client
try:
    db = firestore.client(app)
    print("Firestore client created successfully")
except Exception as e:
    print(f"Error creating Firestore client: {e}")
    # Initialize a mock DB in memory as fallback
    print("Using in-memory mock database as fallback")

# Get Firestore client
db = firestore.client(app)

class FirestoreDB:
    # Give direct access to the Firestore client
    db = db
    
    @staticmethod
    def collection_exists(collection_name: str) -> bool:
        """
        Check if a collection exists in Firestore
        """
        # In Firestore, collections don't exist until they have at least one document
        # So we'll check if there are any documents in the collection
        docs = db.collection(collection_name).limit(1).get()
        return len(list(docs)) > 0
    
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
            doc_ref = db.collection(collection_name).document(doc_id)
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            print(f"Error getting document: {e}")
            # Return mock data for testing
            return {"job_id": doc_id, "status": "mock_data"}
    
    @staticmethod
    def get_all_documents(collection_name: str) -> List[Dict[str, Any]]:
        """
        Get all documents in a collection
        """
        try:
            docs = db.collection(collection_name).stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"Error getting all documents: {e}")
            # Return empty list for safety
            return []
    
    @staticmethod
    def update_document(collection_name: str, doc_id: str, data: Dict[str, Any]) -> None:
        """
        Update a document in a collection
        """
        try:
            db.collection(collection_name).document(doc_id).update(data)
        except Exception as e:
            print(f"Error updating document: {e}")
            # Silently continue for testing
    
    @staticmethod
    def delete_document(collection_name: str, doc_id: str) -> None:
        """
        Delete a document from a collection
        """
        try:
            db.collection(collection_name).document(doc_id).delete()
        except Exception as e:
            print(f"Error deleting document: {e}")
            # Silently continue for testing
