import firebase_admin
from firebase_admin import credentials, firestore
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import json

def replicate_firebase_to_chroma():
    # Step 1: Initialize Firebase
    cred = credentials.Certificate("D:\\dev\\docusign-interview-agent\\firebase_service_account.json")  # Replace with your Firebase credentials path
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    print("Firebase initialized successfully")

    # Step 2: Initialize ChromaDB
    chroma_client = chromadb.Client(Settings(
        chroma_db_impl="duckdb+parquet",
        persist_directory="./chroma_db"
    ))

    print("ChromaDB initialized successfully")

    # Step 3: Initialize the embedding model
    model = SentenceTransformer('all-MiniLM-L6-v2')  # This model creates 384-dimensional embeddings
    print("Embedding model loaded successfully")

    # Step 4: Get all collections from Firebase
    collections = db.collections()
    collection_names = [collection.id for collection in collections]
    print(f"Found {len(collection_names)} collections in Firebase: {collection_names}")

    # Step 5: Process each collection
    for collection_name in collection_names:
        print(f"Processing collection: {collection_name}")

        # Get all documents from the collection
        docs = db.collection(collection_name).stream()
        documents = []
        for doc in docs:
            doc_dict = doc.to_dict()
            doc_dict['_id'] = doc.id  # Store the document ID
            documents.append(doc_dict)

        print(f"Found {len(documents)} documents in collection {collection_name}")

        if not documents:
            print(f"Skipping empty collection: {collection_name}")
            continue

        # Create or get collection in ChromaDB
        try:
            # Try to create a new collection
            chroma_collection = chroma_client.create_collection(name=collection_name)
            print(f"Created new ChromaDB collection: {collection_name}")
        except ValueError:
            # Collection already exists, get it
            chroma_collection = chroma_client.get_collection(name=collection_name)
            print(f"Using existing ChromaDB collection: {collection_name}")

        # Process documents in batches to avoid memory issues
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i+batch_size]
            print(f"Processing batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1}")

            # Prepare data for ChromaDB
            ids = [f"{collection_name}_{doc.get('_id', i+j)}" for j, doc in enumerate(batch)]

            # Convert documents to string for embedding
            doc_texts = [json.dumps(doc) for doc in batch]

            # Generate embeddings
            embeddings = model.encode(doc_texts)

            # Add documents to ChromaDB
            chroma_collection.add(
                embeddings=embeddings.tolist(),
                documents=doc_texts,
                metadatas=batch,
                ids=ids
            )

            print(f"Added {len(batch)} documents to ChromaDB collection {collection_name}")

    # Step 6: Persist the database
    chroma_client.persist()
    print("ChromaDB persisted successfully")

    return chroma_client

def query_example(chroma_client, collection_name, query_text):
    """Example function to query the replicated database"""
    model = SentenceTransformer('all-MiniLM-L6-v2')
    collection = chroma_client.get_collection(name=collection_name)

    # Generate embedding for the query
    query_embedding = model.encode(query_text).tolist()

    # Query the collection
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=5
    )

    print(f"Query results for '{query_text}':")
    for i, (doc, metadata, distance) in enumerate(zip(
        results['documents'][0], 
        results['metadatas'][0],
        results['distances'][0]
    )):
        print(f"Result {i+1} (distance: {distance}):")
        print(f"Metadata: {metadata}")
        print("---")

    return results

# Execute the replication
if __name__ == "__main__":
    try:
        chroma_client = replicate_firebase_to_chroma()

        # Example: Query one of your collections
        # Uncomment and modify the line below to test a query
        # query_example(chroma_client, "your_collection_name", "your query text")

        print("Replication completed successfully")
    except Exception as e:
        print(f"Error during replication: {e}")