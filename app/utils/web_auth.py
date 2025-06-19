"""
Web authentication utilities for Firebase integration
"""
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Firebase configuration with hardcoded values to ensure it works
FIREBASE_CONFIG = {
    'apiKey': "AIzaSyB7mT5f1qlQpT9QaF_wzmDkM0l9RY-MT_Y",
    'authDomain': "login-91de6.firebaseapp.com",
    'projectId': "login-91de6",
    'storageBucket': "login-91de6.firebasestorage.app",
    'messagingSenderId': "873127586938",
    'appId': "1:873127586938:web:359dff24f2790270681fc3"
}

def get_firebase_config() -> Dict[str, Any]:
    """
    Get Firebase configuration for client-side initialization

    Returns:
        Dict[str, Any]: Firebase configuration object
    """
    return FIREBASE_CONFIG


# Frontend script template for initializing Firebase
FIREBASE_INIT_SCRIPT = """
// Firebase initialization
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: "${FIREBASE_API_KEY}",
  authDomain: "${FIREBASE_AUTH_DOMAIN}",
  projectId: "${FIREBASE_PROJECT_ID}",
  storageBucket: "${FIREBASE_STORAGE_BUCKET}",
  messagingSenderId: "${FIREBASE_MESSAGING_SENDER_ID}",
  appId: "${FIREBASE_APP_ID}"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

export { app, auth, db };
"""


def get_firebase_init_script(template_vars: Optional[Dict[str, str]] = None) -> str:
    """
    Generate a Firebase initialization script for frontend use

    Args:
        template_vars: Optional dictionary of template variables to substitute

    Returns:
        str: Firebase initialization script
    """
    script = FIREBASE_INIT_SCRIPT
    
    # Use hardcoded values to ensure it works
    vars_to_substitute = {
        'FIREBASE_API_KEY': "AIzaSyB7mT5f1qlQpT9QaF_wzmDkM0l9RY-MT_Y",
        'FIREBASE_AUTH_DOMAIN': "login-91de6.firebaseapp.com",
        'FIREBASE_PROJECT_ID': "login-91de6",
        'FIREBASE_STORAGE_BUCKET': "login-91de6.firebasestorage.app",
        'FIREBASE_MESSAGING_SENDER_ID': "873127586938",
        'FIREBASE_APP_ID': "1:873127586938:web:359dff24f2790270681fc3"
    }
    
    # Override with any provided template variables
    if template_vars:
        vars_to_substitute.update(template_vars)
    
    # Substitute variables in template
    for key, value in vars_to_substitute.items():
        script = script.replace(f"${{{key}}}", value)
    
    return script


def create_firebase_init_file(output_path: str) -> None:
    """
    Create a Firebase initialization file for frontend use

    Args:
        output_path: Path where the initialization file will be created
    """
    script = get_firebase_init_script()
    
    # Create directories if they don't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Write the script to the file
    with open(output_path, 'w') as f:
        f.write(script)
