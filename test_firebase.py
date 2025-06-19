import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_firebase_connection():
    """Test Firebase connection and permissions"""
    try:
        # Get the path to the service account file
        service_account_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'app/config/service_account.json')
        project_id = os.environ.get('FIREBASE_PROJECT_ID', 'login-91de6')
        
        print(f"Using service account path: {service_account_path}")
        print(f"Using project ID: {project_id}")
        
        # Initialize Firebase app with explicit credentials
        cred = credentials.Certificate(service_account_path)
        app = firebase_admin.initialize_app(
            cred,
            {
                'projectId': project_id,
            },
            name='test-app'  # Use a unique name to avoid conflicts
        )
        
        print("Firebase app initialized successfully")
        
        # Get Firestore client
        db = firestore.client(app)
        print("Firestore client created successfully")
        
        # Try to create a test document
        test_data = {
            'test': True,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'message': 'This is a test document'
        }
        
        print("Attempting to write test document...")
        doc_ref = db.collection('test_collection').document('test_doc')
        doc_ref.set(test_data)
        print("Successfully wrote test document!")
        
        # Try to read the test document
        print("Attempting to read test document...")
        doc = doc_ref.get()
        if doc.exists:
            print(f"Document data: {doc.to_dict()}")
        else:
            print("Document does not exist!")
        
        # Delete the test document
        print("Attempting to delete test document...")
        doc_ref.delete()
        print("Test document deleted successfully!")
        
        # Clean up
        firebase_admin.delete_app(app)
        print("Firebase test completed successfully!")
        
        return True
    except Exception as e:
        print(f"Firebase test failed: {e}")
        # Try to clean up even if there was an error
        try:
            firebase_admin.delete_app(app)
        except:
            pass
        return False

if __name__ == "__main__":
    test_firebase_connection()
