"""
Smart LMS - Auth Router
Registration, login, profile management endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.models import User, UserRole, Gamification
from app.schemas.auth import (
    RegisterRequest, LoginRequest, GoogleLoginRequest, TokenResponse,
    UserResponse, UserUpdate, PasswordChange
)
from app.services.auth_service import (
    hash_password, verify_password, create_access_token,
    authenticate_user, get_user_by_username, get_user_by_email,
    verify_google_token
)
from app.middleware.auth import get_current_user
from app.services.debug_logger import debug_logger

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user"""
    # Check existing
    if await get_user_by_username(db, request.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    if await get_user_by_email(db, request.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    # Validate role
    if request.role not in ["student", "teacher"]:
        raise HTTPException(status_code=400, detail="Role must be 'student' or 'teacher'")

    # Create user
    user = User(
        username=request.username,
        email=request.email,
        password_hash=hash_password(request.password),
        role=UserRole(request.role),
        full_name=request.full_name,
    )
    db.add(user)
    await db.flush()

    # Create gamification profile for students
    if request.role == "student":
        gamification = Gamification(user_id=user.id)
        db.add(gamification)

    await db.commit()
    await db.refresh(user)

    # Generate token
    token = create_access_token({"sub": user.id, "role": user.role.value})

    debug_logger.log("activity", f"User registered: {user.username} ({user.role.value})",
                     user_id=user.id)

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with username/email and password"""
    user = await authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or account locked"
        )

    token = create_access_token({"sub": user.id, "role": user.role.value})

    debug_logger.log("activity", f"User logged in: {user.username}",
                     user_id=user.id)

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


@router.post("/google", response_model=TokenResponse)
async def google_login(request: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    """Login or register with Google ID token"""
    idinfo = verify_google_token(request.id_token)
    if not idinfo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )
    
    email = idinfo['email']
    google_id = idinfo['sub']
    full_name = idinfo.get('name', email.split('@')[0])
    avatar_url = idinfo.get('picture')

    # 1. Try finding by google_id
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    # 2. Try finding by email
    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            # Link google_id to existing account
            user.google_id = google_id
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
            await db.commit()

    # 3. Create new user if not found
    if not user:
        username = email.split('@')[0]
        # Ensure username uniqueness
        from app.services.auth_service import get_user_by_username
        existing_user = await get_user_by_username(db, username)
        if existing_user:
            import uuid
            username = f"{username}_{str(uuid.uuid4())[:5]}"
            
        user = User(
            username=username,
            email=email,
            password_hash=None, # No password for Google users
            google_id=google_id,
            full_name=full_name,
            avatar_url=avatar_url,
            role=UserRole(request.role)
        )
        db.add(user)
        await db.flush()
        
        # Create gamification profile for students
        if user.role == UserRole.STUDENT:
            gamification = Gamification(user_id=user.id)
            db.add(gamification)
            
        await db.commit()
        await db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    from datetime import datetime
    user.last_login = datetime.utcnow()
    await db.commit()

    token = create_access_token({"sub": user.id, "role": user.role.value})
    
    debug_logger.log("activity", f"User logged in via Google: {user.username}", 
                     user_id=user.id)

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_profile(
    updates: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile"""
    if updates.full_name is not None:
        current_user.full_name = updates.full_name
    if updates.email is not None:
        existing = await get_user_by_email(db, updates.email)
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.email = updates.email
    if updates.bio is not None:
        current_user.bio = updates.bio
    if updates.avatar_url is not None:
        current_user.avatar_url = updates.avatar_url

    await db.commit()
    await db.refresh(current_user)

    debug_logger.log("activity", f"Profile updated: {current_user.username}",
                     user_id=current_user.id)

    return UserResponse.model_validate(current_user)


@router.post("/change-password")
async def change_password(
    request: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change user password"""
    if not verify_password(request.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.password_hash = hash_password(request.new_password)
    await db.commit()

    debug_logger.log("activity", f"Password changed: {current_user.username}",
                     user_id=current_user.id)

    return {"message": "Password updated successfully"}
