"""
This module is deprecated.
Firebase initialization is now handled in app/database/firebase_db.py
"""
from firebase_admin import get_app

def initialize_firebase():
    """
    Returns the existing Firebase app
    This function is kept for backward compatibility.
    """
    return get_app()
