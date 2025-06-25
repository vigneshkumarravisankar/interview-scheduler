"""
Firebase to ChromaDB Migration Script
Imports ALL collections and documents from Firebase into ChromaDB for RAG functionality
Uses firebase_service_account_interview_agent.json
"""

import os
import json
from typing import Dict, Any, List
from datetime import datetime

# Firebase imports
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    print("❌ Firebase dependencies not available")
    FIREBASE_AVAILABLE = False

# ChromaDB imports
from app.database.chroma_db import ChromaVectorDB

class FirebaseToChromaMigrator:
    """Migrates ALL Firebase collections to ChromaDB"""
    
    def __init__(self):
        self.chroma_db = ChromaVectorDB()
        self.firebase_db = None
        
        if FIREBASE_AVAILABLE:
            self._initialize_firebase()
    
    def _initialize_firebase(self):
        """Initialize Firebase using the service account file"""
        try:
            service_account_path = "firebase_service_account_interview_agent.json"
            
            if not os.path.exists(service_account_path):
                print(f"❌ Service account file not found: {service_account_path}")
                return
            
            # Initialize Firebase Admin SDK
            if not firebase_admin._apps:
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                print("✅ Firebase initialized with service account")
            
            self.firebase_db = firestore.client()
            print("✅ Firestore client connected")
            
        except Exception as e:
            print(f"❌ Error initializing Firebase: {e}")
            self.firebase_db = None
    
    def discover_all_collections(self) -> List[str]:
        """Discover all collections in Firebase"""
        if not self.firebase_db:
            return []
        
        try:
            collections = []
            for collection in self.firebase_db.collections():
                collections.append(collection.id)
                print(f"📁 Found collection: {collection.id}")
            
            return collections
            
        except Exception as e:
            print(f"❌ Error discovering collections: {e}")
            return []
    
    def migrate_all_collections(self):
        """Import ALL Firebase collections into ChromaDB"""
        if not self.firebase_db:
            print("❌ Firebase not available - cannot import data")
            return
        
        print("🔍 Discovering all Firebase collections...")
        collections = self.discover_all_collections()
        
        if not collections:
            print("⚠️ No collections found in Firebase")
            return
        
        print(f"\n📊 Found {len(collections)} collections:")
        for collection in collections:
            print(f"  📁 {collection}")
        
        print(f"\n🚀 Starting migration of ALL collections...")
        print("=" * 80)
        
        total_documents = 0
        migration_summary = {}
        
        for collection_name in collections:
            try:
                print(f"\n🔄 Migrating: {collection_name}")
                doc_count = self.migrate_collection(collection_name)
                total_documents += doc_count
                migration_summary[collection_name] = doc_count
                
                if doc_count > 0:
                    print(f"✅ {collection_name}: {doc_count} documents migrated")
                else:
                    print(f"⚠️ {collection_name}: No documents found")
                    
            except Exception as e:
                print(f"❌ Error migrating {collection_name}: {e}")
                migration_summary[collection_name] = 0
        
        # Print migration summary
        print(f"\n" + "=" * 80)
        print("🎉 FIREBASE TO CHROMADB MIGRATION COMPLETE!")
        print("=" * 80)
        print(f"📊 SUMMARY:")
        print(f"   🔢 Total collections: {len(collections)}")
        print(f"   📄 Total documents migrated: {total_documents}")
        
        print(f"\n📋 COLLECTION BREAKDOWN:")
        for collection, count in migration_summary.items():
            status = "✅" if count > 0 else "⚠️"
            print(f"   {status} {collection:<25} {count:>6} documents")
        
        # Verify ChromaDB
        self.verify_chromadb_data()
    
    def migrate_collection(self, collection_name: str) -> int:
        """Migrate a specific Firebase collection to ChromaDB"""
        if not self.firebase_db:
            return 0
        
        try:
            # Get all documents from Firebase collection
            docs = self.firebase_db.collection(collection_name).stream()
            
            migrated_count = 0
            
            for doc in docs:
                try:
                    doc_data = doc.to_dict()
                    doc_id = doc.id
                    
                    # Ensure document has an ID field
                    if 'id' not in doc_data:
                        doc_data['id'] = doc_id
                    
                    # Add migration metadata
                    doc_data['_migrated_at'] = datetime.now().isoformat()
                    doc_data['_source'] = 'firebase_import'
                    doc_data['_firebase_collection'] = collection_name
                    doc_data['_firebase_doc_id'] = doc_id
                    
                    # Import into ChromaDB
                    self.chroma_db.create_document_with_id(collection_name, doc_id, doc_data)
                    migrated_count += 1
                    
                    # Progress indicator
                    if migrated_count % 25 == 0:
                        print(f"   📄 Processed {migrated_count} documents...")
                    
                except Exception as e:
                    print(f"   ⚠️ Error migrating document {doc.id}: {e}")
            
            return migrated_count
            
        except Exception as e:
            print(f"❌ Error accessing collection {collection_name}: {e}")
            return 0
    
    def verify_chromadb_data(self):
        """Verify that data was properly imported into ChromaDB"""
        print(f"\n🔍 VERIFYING CHROMADB DATA:")
        
        try:
            chroma_collections = self.chroma_db.list_collections()
            print(f"   📁 ChromaDB collections: {len(chroma_collections)}")
            
            total_docs_in_chroma = 0
            
            for collection in chroma_collections:
                try:
                    stats = self.chroma_db.get_collection_stats(collection)
                    doc_count = stats['document_count']
                    total_docs_in_chroma += doc_count
                    print(f"   📊 {collection:<25} {doc_count:>6} documents")
                    
                    # Test a sample search if documents exist
                    if doc_count > 0:
                        sample_docs = self.chroma_db.semantic_search(
                            collection_name=collection,
                            query_text="test search",
                            n_results=1
                        )
                        if sample_docs:
                            print(f"   ✅ {collection}: RAG search working")
                        
                except Exception as e:
                    print(f"   ❌ Error verifying {collection}: {e}")
            
            print(f"\n📊 VERIFICATION SUMMARY:")
            print(f"   🔢 Total documents in ChromaDB: {total_docs_in_chroma}")
            print(f"   ✅ ChromaDB ready for RAG functionality")
            
        except Exception as e:
            print(f"❌ Error verifying ChromaDB data: {e}")
    
    def show_sample_data(self):
        """Show sample data from each collection"""
        print(f"\n🔍 SAMPLE DATA FROM EACH COLLECTION:")
        
        collections = self.chroma_db.list_collections()
        
        for collection in collections:
            try:
                # Get a sample document
                all_docs = self.chroma_db.get_all_documents(collection)
                if all_docs:
                    sample_doc = all_docs[0]
                    print(f"\n📄 Sample from {collection}:")
                    
                    # Show key fields
                    key_fields = ['id', 'name', 'title', 'email', 'job_role_name', 'status']
                    for field in key_fields:
                        if field in sample_doc:
                            value = str(sample_doc[field])[:50]
                            print(f"   {field}: {value}")
                    
                    print(f"   📊 Total fields: {len(sample_doc)}")
                else:
                    print(f"⚠️ No documents found in {collection}")
                    
            except Exception as e:
                print(f"❌ Error sampling {collection}: {e}")

def run_migration():
    """Run the Firebase import process"""
    print("🚀 FIREBASE TO CHROMADB IMPORT")
    print("=" * 80)
    print("📥 Importing ALL collections and documents from Firebase...")
    print("🎯 Using: firebase_service_account_interview_agent.json")
    print("=" * 80)
    
    migrator = FirebaseToChromaMigrator()
    
    if not migrator.firebase_db:
        print("❌ Cannot connect to Firebase. Please check:")
        print("   1. firebase_service_account_interview_agent.json exists")
        print("   2. Firebase credentials are valid")
        print("   3. Network connection is working")
        return
    
    # Run the migration
    migrator.migrate_all_collections()
    
    # Show sample data
    migrator.show_sample_data()
    
    print(f"\n" + "=" * 80)
    print("✅ IMPORT COMPLETE - ChromaDB ready for RAG!")
    print("🚀 You can now use RAG-enhanced queries with your Firebase data")
    print("=" * 80)

if __name__ == "__main__":
    run_migration()
