from typing import Dict, Any, Optional, List
import uuid


class MockDB:
    """
    In-memory database for testing and development
    Implements the same interface as FirestoreDB
    """
    
    # In-memory storage
    _collections: Dict[str, Dict[str, Dict[str, Any]]] = {}
    
    @classmethod
    def collection_exists(cls, collection_name: str) -> bool:
        """
        Check if a collection exists
        """
        return collection_name in cls._collections
    
    @classmethod
    def create_document(cls, collection_name: str, document_data: Dict[str, Any]) -> str:
        """
        Create a new document in a collection
        Returns the document ID
        """
        try:
            # Create collection if it doesn't exist
            if collection_name not in cls._collections:
                cls._collections[collection_name] = {}
            
            # Generate ID if not provided
            doc_id = document_data.get("job_id", str(uuid.uuid4()))
            
            # Store the document
            cls._collections[collection_name][doc_id] = document_data.copy()
            
            print(f"MockDB: Created document {doc_id} in collection {collection_name}")
            
            return doc_id
        except Exception as e:
            print(f"MockDB Error: {e}")
            raise
    
    @classmethod
    def get_document(cls, collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by its ID
        """
        if collection_name not in cls._collections:
            return None
        
        return cls._collections[collection_name].get(doc_id)
    
    @classmethod
    def get_all_documents(cls, collection_name: str) -> List[Dict[str, Any]]:
        """
        Get all documents in a collection
        """
        if collection_name not in cls._collections:
            return []
        
        return list(cls._collections[collection_name].values())
    
    @classmethod
    def update_document(cls, collection_name: str, doc_id: str, data: Dict[str, Any]) -> None:
        """
        Update a document in a collection
        """
        if collection_name not in cls._collections or doc_id not in cls._collections[collection_name]:
            raise ValueError(f"Document {doc_id} not found in collection {collection_name}")
        
        # Update the document
        cls._collections[collection_name][doc_id].update(data)
    
    @classmethod
    def delete_document(cls, collection_name: str, doc_id: str) -> None:
        """
        Delete a document from a collection
        """
        if collection_name in cls._collections and doc_id in cls._collections[collection_name]:
            del cls._collections[collection_name][doc_id]
    
    @classmethod
    def clear(cls) -> None:
        """
        Clear all data (for testing)
        """
        cls._collections = {}
