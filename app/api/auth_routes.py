from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from app.utils.web_auth import get_firebase_config
import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional

# Load environment variables
load_dotenv()

# Create router
router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={404: {"description": "Not found"}},
)

# Authentication models
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserResponse(BaseModel):
    uid: str
    email: str
    name: Optional[str] = None

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

@router.post("/config", status_code=status.HTTP_200_OK)
async def get_firebase_configuration():
    """
    Get Firebase configuration for client-side initialization
    """
    try:
        config = get_firebase_config()
        return {"firebase_config": config}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Firebase configuration: {str(e)}",
        )

@router.get("/status", status_code=status.HTTP_200_OK)
async def auth_status():
    """
    Authentication status endpoint
    """
    try:
        # Check if Firebase is correctly configured
        config = get_firebase_config()
        project_id = config.get('projectId', os.environ.get('VITE_FIREBASE_PROJECT_ID'))
        
        if not project_id:
            return {
                "status": "warning",
                "message": "Firebase project ID not configured",
                "project_id": None
            }
        
        return {
            "status": "ok",
            "message": "Firebase authentication is configured",
            "project_id": project_id
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Firebase authentication error: {str(e)}",
            "project_id": None
        }

# Note: User authentication is handled client-side with Firebase Authentication
# These endpoints are for reference and could be extended with custom functionality
@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_user():
    """
    Register a new user (placeholder for client-side Firebase Auth)
    
    In a real implementation, this endpoint might perform additional server-side
    validations or operations after the client has registered a user with Firebase.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Registration is handled by Firebase Authentication on the client side"
    )

@router.post("/login", response_model=AuthResponse, status_code=status.HTTP_200_OK)
async def login_user():
    """
    Login a user (placeholder for client-side Firebase Auth)
    
    In a real implementation, this endpoint might perform additional server-side
    validations or operations after the client has authenticated a user with Firebase.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authentication is handled by Firebase Authentication on the client side"
    )
