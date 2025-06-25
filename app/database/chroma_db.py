"""
ChromaDB Implementation with RAG Capabilities
This module provides a complete replacement for Firebase with vector database and RAG features
"""

import os
import json
import uuid
import hashlib
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime
import logging

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import numpy as np
from sentence_transformers import SentenceTransformer

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChromaVectorDB:
    """
    ChromaDB implementation with RAG capabilities
    Provides complete CRUD operations and vector search functionality
    """
    
    def __init__(self, persist_directory: str = "./chroma_data"):
        """Initialize ChromaDB client with persistent storage"""
        self.persist_directory = persist_directory
        
        # Create directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Initialize sentence transformer for embeddings
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Cache for collections
        self._collections = {}
        
        logger.info(f"ChromaDB initialized with persistence at: {persist_directory}")
    
    def _get_collection(self, collection_name: str):
        """Get or create a collection with caching"""
        if collection_name not in self._collections:
            try:
                # Try to get existing collection first
                collection = self.client.get_collection(
                    name=collection_name,
                    embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                        model_name="all-MiniLM-L6-v2"
                    )
                )
                logger.info(f"Retrieved existing collection: {collection_name}")
            except Exception as e:
                # Create new collection if it doesn't exist
                try:
                    collection = self.client.create_collection(
                        name=collection_name,
                        embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                            model_name="all-MiniLM-L6-v2"
                        ),
                        metadata={"hnsw:space": "cosine"}
                    )
                    logger.info(f"Created new collection: {collection_name}")
                except Exception as create_error:
                    logger.error(f"Error creating collection {collection_name}: {create_error}")
                    # Try to get it again in case it was created by another process
                    try:
                        collection = self.client.get_collection(
                            name=collection_name,
                            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                                model_name="all-MiniLM-L6-v2"
                            )
                        )
                        logger.info(f"Retrieved collection after creation error: {collection_name}")
                    except Exception as final_error:
                        logger.error(f"Final error getting collection {collection_name}: {final_error}")
                        raise final_error
            
            self._collections[collection_name] = collection
        
        return self._collections[collection_name]
    
    def _prepare_document_text(self, document_data: Dict[str, Any]) -> str:
        """Prepare document text for embedding"""
        # Extract meaningful text from document
        text_parts = []
        
        # Common text fields to include in embeddings
        text_fields = [
            'name', 'title', 'description', 'content', 'summary',
            'job_role_name', 'job_description', 'technical_skills',
            'email', 'phone_no', 'location', 'status', 'message',
            'feedback', 'notes', 'comments', 'expertise'
        ]
        
        for field in text_fields:
            if field in document_data and document_data[field]:
                if isinstance(document_data[field], str):
                    text_parts.append(f"{field}: {document_data[field]}")
                elif isinstance(document_data[field], list):
                    text_parts.append(f"{field}: {', '.join(map(str, document_data[field]))}")
                else:
                    text_parts.append(f"{field}: {str(document_data[field])}")
        
        # Include nested data
        if 'previous_companies' in document_data:
            for company in document_data['previous_companies']:
                if isinstance(company, dict):
                    if 'name' in company:
                        text_parts.append(f"company: {company['name']}")
                    if 'job_responsibilities' in company:
                        text_parts.append(f"responsibilities: {company['job_responsibilities']}")
        
        return " | ".join(text_parts) if text_parts else str(document_data)
    
    def _sanitize_metadata_for_chroma(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize metadata for ChromaDB by converting complex types to JSON strings
        ChromaDB only supports str, int, float, and bool for metadata values
        """
        sanitized_data = {}
        
        for key, value in document_data.items():
            if value is None:
                sanitized_data[key] = ""
            elif isinstance(value, (str, int, float, bool)):
                sanitized_data[key] = value
            elif isinstance(value, (list, dict)):
                # Convert complex objects to JSON strings
                try:
                    sanitized_data[key] = json.dumps(value, default=str)
                except (TypeError, ValueError) as e:
                    logger.warning(f"Could not serialize {key}: {e}, converting to string")
                    sanitized_data[key] = str(value)
            else:
                # Convert other types to string
                sanitized_data[key] = str(value)
        
        return sanitized_data
    
    def _deserialize_metadata_from_chroma(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deserialize metadata from ChromaDB by converting JSON strings back to objects
        """
        deserialized_data = {}
        
        # Internal ChromaDB fields to skip during deserialization
        internal_fields = {'_type', '_id', '_distance', '_similarity_score'}
        
        for key, value in metadata.items():
            # Skip internal ChromaDB fields
            if key in internal_fields:
                deserialized_data[key] = value
                continue
                
            if isinstance(value, str) and value.strip():
                # Try to parse as JSON if it looks like JSON
                if (value.startswith('{') and value.endswith('}')) or (value.startswith('[') and value.endswith(']')):
                    try:
                        deserialized_data[key] = json.loads(value)
                    except (json.JSONDecodeError, ValueError):
                        deserialized_data[key] = value
                else:
                    deserialized_data[key] = value
            else:
                deserialized_data[key] = value
        
        return deserialized_data
    
    @staticmethod
    def collection_exists(collection_name: str) -> bool:
        """Check if a collection exists"""
        try:
            instance = ChromaVectorDB()
            collection = instance.client.get_collection(collection_name)
            count = collection.count()
            return count > 0
        except Exception:
            return False
    
    @staticmethod
    def create_document(collection_name: str, document_data: Dict[str, Any]) -> str:
        """Create a new document in a collection"""
        instance = ChromaVectorDB()
        
        # Generate document ID
        if collection_name == 'jobs':
            doc_id = document_data.get("job_id", str(uuid.uuid4()))
        elif collection_name == 'candidates_data':
            doc_id = str(uuid.uuid4())
        else:
            doc_id = document_data.get("id", str(uuid.uuid4()))
        
        # Ensure ID is in document data
        document_data["id"] = doc_id
        document_data["created_at"] = document_data.get("created_at", datetime.now().isoformat())
        document_data["updated_at"] = datetime.now().isoformat()
        
        return instance.create_document_with_id(collection_name, doc_id, document_data)
    
    def create_document_with_id(self, collection_name: str, doc_id: str, document_data: Dict[str, Any]) -> str:
        """Create a document with a specific ID"""
        try:
            collection = self._get_collection(collection_name)
            
            # Prepare document text for embedding
            document_text = self._prepare_document_text(document_data)
            
            # Ensure document has required fields
            document_data["id"] = doc_id
            document_data["updated_at"] = datetime.now().isoformat()
            
            # Sanitize metadata for ChromaDB
            sanitized_metadata = self._sanitize_metadata_for_chroma(document_data)
            
            # Add document to collection
            collection.add(
                documents=[document_text],
                metadatas=[sanitized_metadata],
                ids=[doc_id]
            )
            
            logger.info(f"Document created in ChromaDB: {doc_id} (collection: {collection_name})")
            return doc_id
            
        except Exception as e:
            logger.error(f"Error creating document in ChromaDB: {e}")
            return doc_id
    
    @staticmethod
    def get_document(collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by its ID"""
        try:
            instance = ChromaVectorDB()
            collection = instance._get_collection(collection_name)
            
            result = collection.get(ids=[doc_id])
            if result and result['metadatas'] and len(result['metadatas']) > 0:
                # Deserialize metadata back to original format
                return instance._deserialize_metadata_from_chroma(result['metadatas'][0])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting document from ChromaDB: {e}")
            return None
    
    @staticmethod
    def get_all_documents(collection_name: str) -> List[Dict[str, Any]]:
        """Get all documents in a collection"""
        try:
            instance = ChromaVectorDB()
            collection = instance._get_collection(collection_name)
            
            # Get all documents (ChromaDB has a limit, so we'll need to paginate)
            result = collection.get()
            if result['metadatas']:
                # Deserialize all metadata back to original format
                return [instance._deserialize_metadata_from_chroma(metadata) for metadata in result['metadatas']]
            return []
            
        except Exception as e:
            logger.error(f"Error getting all documents from ChromaDB: {e}")
            return []
    
    @staticmethod
    def update_document(collection_name: str, doc_id: str, data: Dict[str, Any]) -> None:
        """Update a document in a collection"""
        try:
            instance = ChromaVectorDB()
            collection = instance._get_collection(collection_name)
            
            # Get existing document
            existing_result = collection.get(ids=[doc_id])
            if not existing_result or not existing_result['metadatas']:
                logger.warning(f"Document {doc_id} not found for update")
                return
            
            # Deserialize existing data first, then merge with updates
            existing_data = instance._deserialize_metadata_from_chroma(existing_result['metadatas'][0])
            updated_data = {**existing_data, **data}
            updated_data["updated_at"] = datetime.now().isoformat()
            
            # Prepare updated text for embedding
            document_text = instance._prepare_document_text(updated_data)
            
            # Sanitize metadata for ChromaDB
            sanitized_metadata = instance._sanitize_metadata_for_chroma(updated_data)
            
            # Update the document
            collection.update(
                ids=[doc_id],
                documents=[document_text],
                metadatas=[sanitized_metadata]
            )
            
            logger.info(f"Document updated in ChromaDB: {doc_id}")
            
        except Exception as e:
            logger.error(f"Error updating document in ChromaDB: {e}")
    
    @staticmethod
    def delete_document(collection_name: str, doc_id: str) -> None:
        """Delete a document from a collection"""
        try:
            instance = ChromaVectorDB()
            collection = instance._get_collection(collection_name)
            
            collection.delete(ids=[doc_id])
            logger.info(f"Document deleted from ChromaDB: {doc_id}")
            
        except Exception as e:
            logger.error(f"Error deleting document from ChromaDB: {e}")
    
    @staticmethod
    def execute_query(collection_name: str, field_path: str, operator: str, value: Any) -> List[Dict[str, Any]]:
        """Execute a simple query against a collection"""
        try:
            instance = ChromaVectorDB()
            collection = instance._get_collection(collection_name)
            
            # Get all documents and filter in memory (ChromaDB doesn't support complex queries like Firestore)
            result = collection.get()
            documents = result['metadatas'] if result['metadatas'] else []
            
            filtered_docs = []
            for doc in documents:
                # Deserialize document first
                deserialized_doc = instance._deserialize_metadata_from_chroma(doc)
                
                if field_path in deserialized_doc:
                    doc_value = deserialized_doc[field_path]
                    
                    # Apply operator
                    if operator == "==" and doc_value == value:
                        filtered_docs.append(deserialized_doc)
                    elif operator == "!=" and doc_value != value:
                        filtered_docs.append(deserialized_doc)
                    elif operator == ">" and doc_value > value:
                        filtered_docs.append(deserialized_doc)
                    elif operator == "<" and doc_value < value:
                        filtered_docs.append(deserialized_doc)
                    elif operator == ">=" and doc_value >= value:
                        filtered_docs.append(deserialized_doc)
                    elif operator == "<=" and doc_value <= value:
                        filtered_docs.append(deserialized_doc)
                    elif operator == "array_contains" and isinstance(doc_value, list) and value in doc_value:
                        filtered_docs.append(deserialized_doc)
                    elif operator == "in" and isinstance(value, list) and doc_value in value:
                        filtered_docs.append(deserialized_doc)
            
            return filtered_docs
            
        except Exception as e:
            logger.error(f"Error executing query in ChromaDB: {e}")
            return []
    
    @staticmethod
    def execute_complex_query(collection_name: str, conditions: List[Tuple[str, str, Any]], order_by: Optional[List[Tuple[str, str]]] = None) -> List[Dict[str, Any]]:
        """Execute a complex query with multiple conditions"""
        try:
            instance = ChromaVectorDB()
            collection = instance._get_collection(collection_name)
            
            # Get all documents and filter in memory
            result = collection.get()
            documents = result['metadatas'] if result['metadatas'] else []
            
            filtered_docs = []
            for doc in documents:
                # Deserialize document first
                deserialized_doc = instance._deserialize_metadata_from_chroma(doc)
                meets_all_conditions = True
                
                for field_path, operator, value in conditions:
                    if field_path not in deserialized_doc:
                        meets_all_conditions = False
                        break
                    
                    doc_value = deserialized_doc[field_path]
                    
                    # Apply operator
                    if operator == "==" and doc_value != value:
                        meets_all_conditions = False
                        break
                    elif operator == "!=" and doc_value == value:
                        meets_all_conditions = False
                        break
                    elif operator == ">" and doc_value <= value:
                        meets_all_conditions = False
                        break
                    elif operator == "<" and doc_value >= value:
                        meets_all_conditions = False
                        break
                    elif operator == ">=" and doc_value < value:
                        meets_all_conditions = False
                        break
                    elif operator == "<=" and doc_value > value:
                        meets_all_conditions = False
                        break
                    elif operator == "array_contains" and (not isinstance(doc_value, list) or value not in doc_value):
                        meets_all_conditions = False
                        break
                    elif operator == "in" and (not isinstance(value, list) or doc_value not in value):
                        meets_all_conditions = False
                        break
                
                if meets_all_conditions:
                    filtered_docs.append(deserialized_doc)
            
            # Apply ordering if specified
            if order_by:
                for field_path, direction in reversed(order_by):
                    reverse = direction.lower() == 'desc'
                    filtered_docs.sort(key=lambda x: x.get(field_path, ''), reverse=reverse)
            
            return filtered_docs
            
        except Exception as e:
            logger.error(f"Error executing complex query in ChromaDB: {e}")
            return []
    
    def semantic_search(self, collection_name: str, query_text: str, n_results: int = 10, where: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Perform semantic search using vector embeddings"""
        try:
            collection = self._get_collection(collection_name)
            
            # Perform vector search
            results = collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where
            )
            
            documents = []
            if results['metadatas'] and len(results['metadatas']) > 0:
                for i, metadata in enumerate(results['metadatas'][0]):
                    # Deserialize metadata first
                    doc = self._deserialize_metadata_from_chroma(metadata)
                    if results['distances'] and len(results['distances']) > 0:
                        doc['_similarity_score'] = 1 - results['distances'][0][i]  # Convert distance to similarity
                    documents.append(doc)
            
            return documents
            
        except Exception as e:
            logger.error(f"Error performing semantic search: {e}")
            return []
    
    def rag_search(self, collection_name: str, query: str, n_results: int = 5) -> Dict[str, Any]:
        """Perform RAG (Retrieval-Augmented Generation) search"""
        try:
            # Get relevant documents using semantic search
            relevant_docs = self.semantic_search(collection_name, query, n_results)
            
            # Prepare context for generation
            context_parts = []
            for doc in relevant_docs:
                doc_text = self._prepare_document_text(doc)
                similarity = doc.get('_similarity_score', 0)
                context_parts.append({
                    'text': doc_text,
                    'metadata': doc,
                    'similarity': similarity
                })
            
            return {
                'query': query,
                'relevant_documents': context_parts,
                'context': '\n\n'.join([part['text'] for part in context_parts]),
                'document_count': len(relevant_docs)
            }
            
        except Exception as e:
            logger.error(f"Error performing RAG search: {e}")
            return {
                'query': query,
                'relevant_documents': [],
                'context': '',
                'document_count': 0
            }
    
    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """Get statistics about a collection"""
        try:
            collection = self._get_collection(collection_name)
            count = collection.count()
            
            return {
                'name': collection_name,
                'document_count': count,
                'created_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {
                'name': collection_name,
                'document_count': 0,
                'error': str(e)
            }
    
    def list_collections(self) -> List[str]:
        """List all collections"""
        try:
            collections = self.client.list_collections()
            return [col.name for col in collections]
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            return []
    
    def reset_collection(self, collection_name: str) -> bool:
        """Reset (delete all documents from) a collection"""
        try:
            self.client.delete_collection(collection_name)
            # Remove from cache
            if collection_name in self._collections:
                del self._collections[collection_name]
            logger.info(f"Collection {collection_name} reset successfully")
            return True
        except Exception as e:
            logger.error(f"Error resetting collection {collection_name}: {e}")
            return False

# Maintain compatibility with existing code
# Create class alias for backward compatibility
class FirestoreDB:
    """Compatibility class that maps to ChromaVectorDB"""
    
    # Map all static methods to ChromaVectorDB
    collection_exists = ChromaVectorDB.collection_exists
    create_document = ChromaVectorDB.create_document
    create_document_with_id = ChromaVectorDB.create_document_with_id
    get_document = ChromaVectorDB.get_document
    get_all_documents = ChromaVectorDB.get_all_documents
    update_document = ChromaVectorDB.update_document
    delete_document = ChromaVectorDB.delete_document
    execute_query = ChromaVectorDB.execute_query
    execute_complex_query = ChromaVectorDB.execute_complex_query
    
    # Direct access to ChromaDB instance
    @staticmethod
    def get_db():
        return ChromaVectorDB()

# Create a global instance for easy access
chroma_db = ChromaVectorDB()

# Alias for backward compatibility
db = chroma_db
