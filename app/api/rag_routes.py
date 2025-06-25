"""
RAG (Retrieval-Augmented Generation) API Routes

This module provides RAG-specific endpoints for querying the ChromaDB vector database
with semantic search, spell correction, and intelligent response generation.
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, Optional, List
import uuid
import json
import logging
from datetime import datetime
import re
from difflib import SequenceMatcher
from textblob import TextBlob

from app.database.chroma_db import ChromaVectorDB
from pydantic import BaseModel

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/rag",
    tags=["rag-queries"],
    responses={404: {"description": "Not found"}},
)

class RAGQueryRequest(BaseModel):
    query: str
    collection: Optional[str] = None
    n_results: Optional[int] = 10
    enable_spell_check: Optional[bool] = True
    similarity_threshold: Optional[float] = 0.3

class RAGQueryResponse(BaseModel):
    original_query: str
    corrected_query: Optional[str] = None
    response: str
    relevant_documents: List[Dict[str, Any]]
    similarity_scores: List[float]
    collection_used: str
    spell_corrections: List[Dict[str, str]] = []
    confidence: float
    processing_time_ms: int

class SpellChecker:
    """Enhanced spell checker with domain-specific corrections"""
    
    # Common technical terms and domain-specific words
    TECHNICAL_VOCABULARY = {
        'javascript', 'python', 'java', 'react', 'angular', 'nodejs', 'sql', 'mysql',
        'postgresql', 'mongodb', 'docker', 'kubernetes', 'aws', 'azure', 'github',
        'developer', 'engineer', 'programmer', 'analyst', 'manager', 'coordinator',
        'frontend', 'backend', 'fullstack', 'devops', 'database', 'api', 'rest',
        'graphql', 'microservices', 'agile', 'scrum', 'kanban', 'jira', 'gitlab',
        'resume', 'cv', 'interview', 'candidate', 'recruiter', 'hiring', 'onboarding',
        'salary', 'benefits', 'remote', 'hybrid', 'onsite', 'freelance', 'contract'
    }
    
    # Common misspellings and their corrections
    COMMON_CORRECTIONS = {
        'javascrpit': 'javascript',
        'javascrit': 'javascript',
        'javasript': 'javascript',
        'phyton': 'python',
        'pyhton': 'python',
        'pytohn': 'python',
        'reac': 'react',
        'reactt': 'react',
        'angualr': 'angular',
        'anglar': 'angular',
        'develoepr': 'developer',
        'developr': 'developer',
        'enginer': 'engineer',
        'enginee': 'engineer',
        'candiate': 'candidate',
        'candidat': 'candidate',
        'intervew': 'interview',
        'interveiw': 'interview',
        'reusme': 'resume',
        'resumee': 'resume',
        'salray': 'salary',
        'sallary': 'salary',
        'expereince': 'experience',
        'experiance': 'experience',
        'skillss': 'skills',
        'skils': 'skills',
        'requirments': 'requirements',
        'requirments': 'requirements'
    }
    
    @classmethod
    def correct_spelling(cls, text: str) -> tuple[str, List[Dict[str, str]]]:
        """
        Correct spelling errors in the input text
        
        Returns:
            tuple: (corrected_text, list_of_corrections)
        """
        corrections = []
        words = re.findall(r'\b\w+\b', text.lower())
        corrected_text = text
        
        for word in words:
            # Check direct corrections first
            if word in cls.COMMON_CORRECTIONS:
                correction = cls.COMMON_CORRECTIONS[word]
                corrected_text = re.sub(
                    r'\b' + re.escape(word) + r'\b', 
                    correction, 
                    corrected_text, 
                    flags=re.IGNORECASE
                )
                corrections.append({
                    'original': word,
                    'corrected': correction,
                    'type': 'direct_mapping'
                })
            
            # Skip if word is in technical vocabulary
            elif word.lower() in cls.TECHNICAL_VOCABULARY:
                continue
            
            # Use TextBlob for general spell checking
            else:
                try:
                    blob = TextBlob(word)
                    corrected_word = str(blob.correct())
                    
                    if corrected_word != word and len(corrected_word) > 2:
                        # Calculate similarity to avoid over-correction
                        similarity = SequenceMatcher(None, word, corrected_word).ratio()
                        
                        if similarity > 0.6:  # Only correct if reasonably similar
                            corrected_text = re.sub(
                                r'\b' + re.escape(word) + r'\b', 
                                corrected_word, 
                                corrected_text, 
                                flags=re.IGNORECASE
                            )
                            corrections.append({
                                'original': word,
                                'corrected': corrected_word,
                                'type': 'textblob',
                                'similarity': similarity
                            })
                except Exception as e:
                    logger.warning(f"Error correcting word '{word}': {e}")
        
        return corrected_text, corrections

@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest):
    """
    Perform RAG query with semantic search and spell correction
    
    This endpoint:
    1. Optionally corrects spelling in the query
    2. Performs semantic search across all collections or a specific collection
    3. Generates an intelligent response based on retrieved documents
    4. Returns detailed metadata about the search results
    """
    start_time = datetime.now()
    
    try:
        db = ChromaVectorDB()
        original_query = request.query.strip()
        
        if not original_query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Spell correction
        corrected_query = original_query
        spell_corrections = []
        
        if request.enable_spell_check:
            corrected_query, spell_corrections = SpellChecker.correct_spelling(original_query)
            logger.info(f"Spell check: '{original_query}' -> '{corrected_query}'")
        
        # Determine collections to search
        target_collections = []
        if request.collection:
            target_collections = [request.collection]
        else:
            # Search across all available collections
            available_collections = db.list_collections()
            # Filter out test collections and chat collections
            excluded_prefixes = ['test_', 'chat', 'advanced_chat', 'chatbot_']
            target_collections = [col for col in available_collections 
                                if not any(col.startswith(prefix) for prefix in excluded_prefixes)]
        
        if not target_collections:
            raise HTTPException(status_code=404, detail="No collections found to search")
        
        # Perform semantic search across collections
        all_results = []
        collection_used = None
        
        for collection_name in target_collections:
            try:
                results = db.semantic_search(
                    collection_name=collection_name,
                    query_text=corrected_query,
                    n_results=request.n_results
                )
                
                for result in results:
                    result['_collection'] = collection_name
                    all_results.append(result)
                
                if results:
                    collection_used = collection_name
                    
            except Exception as e:
                logger.warning(f"Error searching collection {collection_name}: {e}")
                continue
        
        if not all_results:
            return RAGQueryResponse(
                original_query=original_query,
                corrected_query=corrected_query if corrected_query != original_query else None,
                response="I couldn't find any relevant information for your query. Please try rephrasing your question or check if the data exists in the system.",
                relevant_documents=[],
                similarity_scores=[],
                collection_used="none",
                spell_corrections=spell_corrections,
                confidence=0.0,
                processing_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
        
        # Sort by similarity score and filter by threshold
        all_results.sort(key=lambda x: x.get('_similarity_score', 0), reverse=True)
        filtered_results = [
            result for result in all_results 
            if result.get('_similarity_score', 0) >= request.similarity_threshold
        ]
        
        if not filtered_results:
            filtered_results = all_results[:3]  # Take top 3 even if below threshold
        
        # Generate intelligent response
        response_text = generate_rag_response(corrected_query, filtered_results[:5])
        
        # Calculate overall confidence
        similarities = [result.get('_similarity_score', 0) for result in filtered_results[:5]]
        avg_confidence = sum(similarities) / len(similarities) if similarities else 0.0
        
        # Prepare response
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return RAGQueryResponse(
            original_query=original_query,
            corrected_query=corrected_query if corrected_query != original_query else None,
            response=response_text,
            relevant_documents=filtered_results[:request.n_results],
            similarity_scores=similarities,
            collection_used=collection_used or target_collections[0],
            spell_corrections=spell_corrections,
            confidence=avg_confidence,
            processing_time_ms=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in RAG query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing RAG query: {str(e)}"
        )


def generate_rag_response(query: str, documents: List[Dict[str, Any]]) -> str:
    """
    Generate an intelligent response based on retrieved documents
    
    This function analyzes the query intent and retrieved documents to generate
    a contextual, helpful response.
    """
    if not documents:
        return "I couldn't find any relevant information for your query."
    
    # Analyze query intent
    query_lower = query.lower()
    
    # Count and summary responses
    if any(word in query_lower for word in ['how many', 'count', 'number of', 'total']):
        count = len(documents)
        response = f"I found {count} relevant result{'s' if count != 1 else ''} for your query."
        
        # Add specific details based on document types
        if documents[0].get('job_role_name'):
            job_roles = list(set(doc.get('job_role_name', 'Unknown') for doc in documents[:5]))
            response += f" The positions include: {', '.join(job_roles[:3])}{'...' if len(job_roles) > 3 else ''}."
        
        elif documents[0].get('name') and documents[0].get('email'):
            response += f" These include candidates with various skills and experience levels."
        
        return response
    
    # List and show responses
    elif any(word in query_lower for word in ['show', 'list', 'find', 'get', 'what are']):
        response_parts = []
        
        # Handle job listings
        if documents[0].get('job_role_name'):
            response_parts.append("Here are the relevant job positions I found:")
            for i, doc in enumerate(documents[:3], 1):
                job_title = doc.get('job_role_name', 'Unknown Position')
                company = doc.get('company_name', 'Company')
                location = doc.get('location', 'Location not specified')
                experience = doc.get('required_experience', 'Experience not specified')
                
                response_parts.append(
                    f"{i}. **{job_title}** at {company} - {location} "
                    f"(Experience: {experience})"
                )
        
        # Handle candidate listings
        elif documents[0].get('name') and documents[0].get('email'):
            response_parts.append("Here are the relevant candidates I found:")
            for i, doc in enumerate(documents[:3], 1):
                name = doc.get('name', 'Unknown Name')
                email = doc.get('email', 'No email')
                skills = doc.get('technical_skills', [])
                experience = doc.get('total_experience', 'Not specified')
                
                skills_text = ', '.join(skills[:3]) if isinstance(skills, list) else str(skills)
                response_parts.append(
                    f"{i}. **{name}** ({email}) - {experience} experience "
                    f"Skills: {skills_text}"
                )
        
        # Handle interview data
        elif documents[0].get('interview_rounds'):
            response_parts.append("Here are the relevant interview records I found:")
            for i, doc in enumerate(documents[:3], 1):
                candidate_name = doc.get('name', 'Unknown Candidate')
                status = doc.get('status', 'Unknown Status')
                rounds = doc.get('interview_rounds', [])
                
                response_parts.append(
                    f"{i}. **{candidate_name}** - Status: {status} "
                    f"({len(rounds) if isinstance(rounds, list) else 0} interview rounds)"
                )
        
        # Generic response for other document types
        else:
            response_parts.append("Here's what I found:")
            for i, doc in enumerate(documents[:3], 1):
                # Try to extract meaningful information
                title = (doc.get('title') or doc.get('name') or 
                        doc.get('job_role_name') or f"Item {i}")
                
                # Get a brief description
                description = ""
                for field in ['description', 'job_description', 'summary', 'content']:
                    if doc.get(field):
                        description = doc[field][:100] + "..." if len(doc[field]) > 100 else doc[field]
                        break
                
                response_parts.append(f"{i}. **{title}**")
                if description:
                    response_parts.append(f"   {description}")
        
        return "\n".join(response_parts)
    
    # Search and filter responses
    elif any(word in query_lower for word in ['with', 'having', 'who has', 'filter', 'search']):
        response = f"I found {len(documents)} items matching your criteria:\n"
        
        for i, doc in enumerate(documents[:3], 1):
            # Extract key information based on document type
            if doc.get('technical_skills'):
                name = doc.get('name', f'Candidate {i}')
                skills = doc.get('technical_skills', [])
                experience = doc.get('total_experience', 'Not specified')
                
                skills_text = ', '.join(skills[:5]) if isinstance(skills, list) else str(skills)
                response += f"{i}. **{name}** - {experience} experience, Skills: {skills_text}\n"
            
            elif doc.get('job_role_name'):
                job_title = doc.get('job_role_name', 'Unknown Position')
                requirements = doc.get('required_skills', [])
                
                req_text = ', '.join(requirements[:3]) if isinstance(requirements, list) else str(requirements)
                response += f"{i}. **{job_title}** - Requirements: {req_text}\n"
        
        return response.strip()
    
    # General informational response
    else:
        # Try to provide a contextual answer
        primary_doc = documents[0]
        
        if primary_doc.get('job_role_name'):
            job_title = primary_doc.get('job_role_name')
            company = primary_doc.get('company_name', 'the company')
            
            response = f"Based on your query, I found information about the **{job_title}** position at {company}. "
            
            if primary_doc.get('job_description'):
                desc = primary_doc['job_description'][:200] + "..." if len(primary_doc['job_description']) > 200 else primary_doc['job_description']
                response += f"Here's what the role involves: {desc}"
            
            return response
        
        elif primary_doc.get('name') and primary_doc.get('email'):
            name = primary_doc.get('name')
            response = f"Based on your query, I found information about **{name}**. "
            
            if primary_doc.get('technical_skills'):
                skills = primary_doc['technical_skills']
                skills_text = ', '.join(skills[:5]) if isinstance(skills, list) else str(skills)
                response += f"Their technical skills include: {skills_text}. "
            
            if primary_doc.get('total_experience'):
                response += f"They have {primary_doc['total_experience']} of experience."
            
            return response
        
        # Generic response
        return (f"I found {len(documents)} relevant result{'s' if len(documents) != 1 else ''} "
                f"for your query. The information includes various details that might be helpful "
                f"for your specific needs.")


@router.get("/collections")
async def list_available_collections():
    """
    List all available collections for RAG queries
    """
    try:
        db = ChromaVectorDB()
        collections = db.list_collections()
        
        # Get stats for each collection
        collection_stats = []
        excluded_prefixes = ['test_', 'chat', 'advanced_chat', 'chatbot_']
        
        for collection_name in collections:
            # Skip test collections and chat collections
            if not any(collection_name.startswith(prefix) for prefix in excluded_prefixes):
                try:
                    stats = db.get_collection_stats(collection_name)
                    collection_stats.append(stats)
                except Exception as e:
                    logger.warning(f"Error getting stats for {collection_name}: {e}")
                    collection_stats.append({
                        'name': collection_name,
                        'document_count': 0,
                        'error': str(e)
                    })
        
        return {
            "collections": collection_stats,
            "total_collections": len(collection_stats),
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error listing collections: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing collections: {str(e)}"
        )


@router.post("/spell-check")
async def spell_check_only(request: Dict[str, str]):
    """
    Perform spell checking only without RAG query
    """
    try:
        text = request.get('text', '').strip()
        if not text:
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        corrected_text, corrections = SpellChecker.correct_spelling(text)
        
        return {
            "original_text": text,
            "corrected_text": corrected_text,
            "corrections": corrections,
            "has_corrections": len(corrections) > 0,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error in spell check: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in spell check: {str(e)}"
        )


@router.get("/health")
async def rag_health_check():
    """
    Health check for RAG system
    """
    try:
        db = ChromaVectorDB()
        collections = db.list_collections()
        
        # Test spell checker
        test_text = "test speling checker"
        corrected, _ = SpellChecker.correct_spelling(test_text)
        
        return {
            "status": "healthy",
            "collections_available": len(collections),
            "spell_checker_working": corrected != test_text,
            "timestamp": datetime.now().isoformat(),
            "success": True
        }
        
    except Exception as e:
        logger.error(f"RAG health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "success": False
        }
