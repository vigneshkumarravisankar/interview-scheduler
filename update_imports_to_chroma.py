"""
Script to update all Firebase imports to ChromaDB across the entire codebase
"""

import os
import glob
from typing import List, Tuple

def find_python_files(directory: str) -> List[str]:
    """Find all Python files in the directory and subdirectories"""
    python_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    return python_files

def update_file_imports(file_path: str) -> bool:
    """Update Firebase imports to ChromaDB imports in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Update Firebase imports to ChromaDB imports
        content = content.replace(
            'from app.database.firebase_db import FirestoreDB',
            'from app.database.chroma_db import FirestoreDB, ChromaVectorDB'
        )
        
        # Also handle direct FirestoreDB imports that might be needed
        if 'from app.database.firebase_db import' in content and 'FirestoreDB' in content:
            # Replace any other firebase_db imports
            content = content.replace(
                'from app.database.firebase_db import',
                'from app.database.chroma_db import'
            )
        
        # Handle specific cases where firebase_db might be imported differently
        content = content.replace(
            'import app.database.firebase_db',
            'import app.database.chroma_db'
        )
        
        content = content.replace(
            'app.database.firebase_db.FirestoreDB',
            'app.database.chroma_db.FirestoreDB'
        )
        
        # Update any remaining references to firebase_db module
        content = content.replace(
            'firebase_db.FirestoreDB',
            'chroma_db.FirestoreDB'
        )
        
        # Save file if changes were made
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False

def main():
    """Main function to update all imports"""
    print("🔄 Starting Firebase to ChromaDB import updates...")
    
    # Find all Python files in the app directory
    app_directory = "./app"
    python_files = find_python_files(app_directory)
    
    updated_files = []
    failed_files = []
    
    for file_path in python_files:
        try:
            if update_file_imports(file_path):
                updated_files.append(file_path)
                print(f"✅ Updated: {file_path}")
            else:
                print(f"⭕ No changes needed: {file_path}")
        except Exception as e:
            failed_files.append((file_path, str(e)))
            print(f"❌ Failed: {file_path} - {e}")
    
    # Summary
    print("\n" + "="*60)
    print("📊 IMPORT UPDATE SUMMARY")
    print("="*60)
    print(f"Total files processed: {len(python_files)}")
    print(f"Files updated: {len(updated_files)}")
    print(f"Files failed: {len(failed_files)}")
    
    if updated_files:
        print("\n✅ Updated files:")
        for file_path in updated_files:
            print(f"  - {file_path}")
    
    if failed_files:
        print("\n❌ Failed files:")
        for file_path, error in failed_files:
            print(f"  - {file_path}: {error}")
    
    print("\n🎉 Import update completed!")
    print("Next step: Run the migration script to transfer data from Firebase to ChromaDB")

if __name__ == "__main__":
    main()
