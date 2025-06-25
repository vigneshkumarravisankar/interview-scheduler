"""
Test Firebase connection using the service account
"""

import os
import sys

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    print("✅ Firebase dependencies available")
except ImportError as e:
    print(f"❌ Firebase dependencies missing: {e}")
    sys.exit(1)

def test_firebase_connection():
    """Test Firebase connection"""
    print("🔧 Testing Firebase connection...")
    
    try:
        # Check if service account file exists
        service_account_path = "firebase_service_account_interview_agent.json"
        
        if not os.path.exists(service_account_path):
            print(f"❌ Service account file not found: {service_account_path}")
            return False
        
        print(f"✅ Service account file found: {service_account_path}")
        
        # Initialize Firebase
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase Admin SDK initialized")
        
        # Test Firestore connection
        db = firestore.client()
        print("✅ Firestore client created")
        
        # Test listing collections
        print("🔍 Discovering collections...")
        collections = []
        for collection in db.collections():
            collections.append(collection.id)
            print(f"   📁 {collection.id}")
        
        print(f"✅ Found {len(collections)} collections")
        
        # Test reading a sample document
        if collections:
            sample_collection = collections[0]
            print(f"🔍 Testing document access in '{sample_collection}'...")
            
            docs = db.collection(sample_collection).limit(1).stream()
            doc_count = 0
            for doc in docs:
                doc_count += 1
                print(f"   📄 Sample document ID: {doc.id}")
                doc_data = doc.to_dict()
                print(f"   📊 Document has {len(doc_data)} fields")
                break
            
            if doc_count == 0:
                print(f"⚠️ No documents found in {sample_collection}")
            else:
                print(f"✅ Successfully accessed documents")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Firebase connection: {e}")
        return False

if __name__ == "__main__":
    print("🚀 FIREBASE CONNECTION TEST")
    print("=" * 50)
    
    success = test_firebase_connection()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Firebase connection test PASSED")
    else:
        print("❌ Firebase connection test FAILED")
