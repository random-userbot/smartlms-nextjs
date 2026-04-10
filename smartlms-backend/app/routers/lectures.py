"""
Smart LMS - Lectures Router
Lecture CRUD, video upload, YouTube import, transcript extraction, and materials.
"""

import asyncio
import os
import tempfile
from uuid import uuid4
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import cloudinary
import cloudinary.uploader

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user, require_teacher_or_admin
from app.models.models import User, UserRole, Course, Lecture, Material
from app.services.debug_logger import debug_logger
from app.services.youtube_service import (
    extract_playlist_videos,
    get_video_transcript,
    normalize_youtube_watch_url,
)
from app.services.summary_service import summary_service
from app.services.storage_service import storage_service

router = APIRouter(prefix="/api/lectures", tags=["Lectures"])

if (
    settings.CLOUDINARY_CLOUD_NAME
    and settings.CLOUDINARY_API_KEY
    and settings.CLOUDINARY_API_SECRET
):
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )


class LectureCreate(BaseModel):
    course_id: str
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    video_url: Optional[str] = None
    youtube_url: Optional[str] = None
    duration: int = 0
    order_index: int = 0


class LectureUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    video_url: Optional[str] = None
    youtube_url: Optional[str] = None
    duration: Optional[int] = None
    order_index: Optional[int] = None
    is_published: Optional[bool] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None


class LectureResponse(BaseModel):
    id: str
    course_id: str
    title: str
    description: Optional[str]
    video_url: Optional[str]
    youtube_url: Optional[str]
    thumbnail_url: Optional[str]
    transcript: Optional[str]
    summary: Optional[str]
    duration: int
    order_index: int
    is_published: bool
    created_at: datetime

    class Config:
        from_attributes = True


class YouTubeImportRequest(BaseModel):
    course_id: str
    playlist_url: str
    import_transcripts: bool = True


class MaterialResponse(BaseModel):
    id: str
    course_id: str
    lecture_id: Optional[str]
    title: str
    file_url: str
    file_type: str
    file_size: int
    created_at: datetime

    class Config:
        from_attributes = True


def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "file")
    return "".join(ch for ch in base if ch.isalnum() or ch in {"-", "_", "."}) or "file"


def _public_media_url(request: Request, rel_path: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/media/{rel_path.lstrip('/')}"


async def _save_uploaded_file(file: UploadFile, subdir: str, max_bytes: int):
    os.makedirs(os.path.join(settings.UPLOAD_DIR, subdir), exist_ok=True)

    safe_name = _safe_filename(file.filename or "upload.bin")
    ext = os.path.splitext(safe_name)[1]
    stored_name = f"{uuid4().hex}{ext}"
    rel_path = os.path.join(subdir, stored_name).replace("\\", "/")
    abs_path = os.path.join(settings.UPLOAD_DIR, subdir, stored_name)

    size = 0
    try:
        with open(abs_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Max {max_bytes // (1024 * 1024)} MB",
                    )
                out.write(chunk)
    except Exception:
        if os.path.exists(abs_path):
            os.remove(abs_path)
        raise
    finally:
        await file.close()

    return rel_path, size


def _cloudinary_configured() -> bool:
    return bool(
        settings.CLOUDINARY_CLOUD_NAME
        and settings.CLOUDINARY_API_KEY
        and settings.CLOUDINARY_API_SECRET
    )


async def _upload_video_to_cloudinary(file: UploadFile, max_bytes: int):
    """Upload lecture video to Cloudinary and return (secure_url, file_size)."""
    if not _cloudinary_configured():
        raise HTTPException(
            status_code=503,
            detail="Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET.",
        )

    safe_name = _safe_filename(file.filename or "lecture_video.mp4")
    ext = os.path.splitext(safe_name)[1] or ".mp4"
    size = 0

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            temp_path = tmp.name

        with open(temp_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Max {max_bytes // (1024 * 1024)} MB",
                    )
                out.write(chunk)

        upload_result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: cloudinary.uploader.upload(
                temp_path,
                resource_type="video",
                folder="smartlms/lectures",
                use_filename=True,
                unique_filename=True,
            ),
        )

        secure_url = upload_result.get("secure_url")
        if not secure_url:
            raise HTTPException(status_code=502, detail="Cloudinary upload failed: missing secure URL")

        return secure_url, size
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


async def _generate_lecture_transcript_background(lecture_id: str, prefer_local: bool = False, force_refresh: bool = False):
    from app.database import async_session

    async with async_session() as session:
        try:
            res = await session.execute(select(Lecture).where(Lecture.id == lecture_id))
            lecture = res.scalar_one_or_none()
            if not lecture:
                return
            
            # Skip if transcript exists and we are not forcing a refresh
            if lecture.transcript and not force_refresh:
                debug_logger.log("activity", f"Skipping transcript generation for {lecture_id} as it already exists.")
                return

            target_url = lecture.youtube_url or lecture.video_url
            if not target_url:
                return

            debug_logger.log("activity", f"Starting background transcription for lecture: {lecture.title} ({target_url})")
            transcript = await get_video_transcript(target_url, prefer_local=prefer_local)
            
            if transcript:
                print(f"[DB] Received transcript of length: {len(transcript)}", flush=True)
                lecture.transcript = transcript
                await session.commit()
                await session.refresh(lecture)
                print(f"[DB] DATABASE COMMIT SUCCESS for: {lecture.title}", flush=True)
                debug_logger.log("activity", f"Transcript committed to DB for: {lecture.title}")
                
                # Generate summary immediately after transcript
                try:
                    summary = await summary_service.summarize_transcript(transcript)
                    if summary:
                        lecture.summary = summary
                        await session.commit()
                        print(f"[DB] SUMMARY COMMIT SUCCESS for: {lecture.title}", flush=True)
                        debug_logger.log("activity", f"Summary generated and committed for: {lecture.title}")
                except Exception as se:
                    print(f"[DB] Summary Error: {se}", flush=True)
                    debug_logger.log("error", f"Summary generation failed for {lecture_id}: {str(se)}")
            else:
                print(f"[DB] Transcript returned EMPTY or null", flush=True)
                debug_logger.log("error", f"Transcript generation returned empty for lecture {lecture_id}")
        except Exception as e:
            print(f"[DB] CRITICAL ERROR in bg task: {e}", flush=True)
            debug_logger.log("error", f"Transcript generation failed for lecture {lecture_id}: {str(e)}")


@router.get("/course/{course_id}", response_model=List[LectureResponse])
async def get_course_lectures(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Lecture).where(Lecture.course_id == course_id)
    if current_user.role == UserRole.STUDENT:
        query = query.where(Lecture.is_published == True)
    
    result = await db.execute(query.order_by(Lecture.order_index))
    lectures = result.scalars().all()
    return [LectureResponse.model_validate(l) for l in lectures]


@router.get("/{lecture_id}", response_model=LectureResponse)
async def get_lecture(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
    lecture = result.scalar_one_or_none()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    return LectureResponse.model_validate(lecture)


@router.post("", response_model=LectureResponse, status_code=201)
async def create_lecture(
    request: LectureCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    course_result = await db.execute(select(Course).where(Course.id == request.course_id))
    course = course_result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.teacher_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not your course")

    if request.order_index == 0:
        count_result = await db.execute(
            select(func.count()).select_from(Lecture).where(Lecture.course_id == request.course_id)
        )
        request.order_index = (count_result.scalar() or 0) + 1

    lecture = Lecture(
        course_id=request.course_id,
        title=request.title,
        description=request.description,
        video_url=request.video_url,
        youtube_url=normalize_youtube_watch_url(request.youtube_url),
        duration=request.duration,
        order_index=request.order_index,
    )
    db.add(lecture)
    await db.commit()
    await db.refresh(lecture)

    if (lecture.youtube_url or lecture.video_url) and not lecture.transcript:
        background_tasks.add_task(_generate_lecture_transcript_background, lecture.id, True)

    debug_logger.log("activity", f"Lecture created: {lecture.title} in course {course.title}", user_id=current_user.id)
    return LectureResponse.model_validate(lecture)


@router.put("/{lecture_id}", response_model=LectureResponse)
async def update_lecture(
    lecture_id: str,
    request: LectureUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    result = await db.execute(select(Lecture).join(Course).where(Lecture.id == lecture_id))
    lecture = result.scalar_one_or_none()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    for field, value in request.model_dump(exclude_unset=True).items():
        if field == "youtube_url":
            value = normalize_youtube_watch_url(value)
        setattr(lecture, field, value)

    should_generate_transcript = bool(lecture.youtube_url) and not lecture.transcript

    await db.commit()
    await db.refresh(lecture)

    if (lecture.youtube_url or lecture.video_url) and not lecture.transcript:
        background_tasks.add_task(_generate_lecture_transcript_background, lecture.id, True)

    debug_logger.log("activity", f"Lecture updated: {lecture.title}", user_id=current_user.id)
    return LectureResponse.model_validate(lecture)


@router.post("/{lecture_id}/upload-video")
async def upload_lecture_video(
    lecture_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    res = await db.execute(select(Lecture).join(Course).where(Lecture.id == lecture_id))
    lecture = res.scalar_one_or_none()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    max_bytes = settings.MAX_VIDEO_UPLOAD_MB * 1024 * 1024
    video_url, file_size = await _upload_video_to_cloudinary(file, max_bytes)
    lecture.video_url = video_url
    lecture.youtube_url = None
    await db.commit()
    await db.refresh(lecture)

    # Trigger transcription for the newly uploaded video
    background_tasks.add_task(_generate_lecture_transcript_background, lecture.id, True)

    return {
        "lecture_id": lecture.id,
        "video_url": lecture.video_url,
        "file_size": file_size,
        "message": "Video uploaded to Cloudinary successfully and transcription started.",
    }


@router.post("/{lecture_id}/generate-transcript")
async def manual_generate_transcript(
    lecture_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Manually trigger AI transcript generation for a lecture."""
    result = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
    lecture = result.scalar_one_or_none()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    if not lecture.youtube_url and not lecture.video_url:
        raise HTTPException(status_code=400, detail="No video source detected for this lecture.")

    # Immediate logging for terminal visibility
    print(f"DEBUG: Manual transcript generation triggered for Lecture: {lecture.title} ({lecture.id})")
    debug_logger.log("activity", f"Manual transcript generation TRIGGERED for lecture: {lecture.title}", user_id=current_user.id)

    background_tasks.add_task(_generate_lecture_transcript_background, lecture.id, True, True)
    return {"message": "Transcription task initiated in the background. Terminal logs will track progress."}


@router.delete("/{lecture_id}")
async def delete_lecture(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    result = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
    lecture = result.scalar_one_or_none()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    await db.delete(lecture)
    await db.commit()

    debug_logger.log("activity", f"Lecture deleted: {lecture.title}", user_id=current_user.id)
    return {"message": "Lecture deleted"}


@router.post("/youtube-import")
async def import_youtube_playlist(
    request: YouTubeImportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    course_result = await db.execute(select(Course).where(Course.id == request.course_id))
    course = course_result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    try:
        videos = await extract_playlist_videos(request.playlist_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import playlist: {str(e)}")

    count_result = await db.execute(
        select(func.count()).select_from(Lecture).where(Lecture.course_id == request.course_id)
    )
    start_index = (count_result.scalar() or 0) + 1

    created_lectures = []
    for i, video in enumerate(videos):
        lecture = Lecture(
            course_id=request.course_id,
            title=video["title"],
            description=video.get("description", ""),
            youtube_url=normalize_youtube_watch_url(video.get("url")),
            thumbnail_url=video.get("thumbnail"),
            duration=video.get("duration", 0),
            order_index=start_index + i,
        )
        db.add(lecture)
        created_lectures.append(lecture)

    await db.commit()

    async def fetch_playlist_transcripts(lecture_ids: List[str]):
        from app.database import async_session

        batch_size = 4
        async with async_session() as session:
            for i, lid in enumerate(lecture_ids, start=1):
                try:
                    res = await session.execute(select(Lecture).where(Lecture.id == lid))
                    lec = res.scalar_one_or_none()
                    if lec and lec.youtube_url and not lec.transcript:
                        transcript = await get_video_transcript(lec.youtube_url, prefer_local=True)
                        if transcript:
                            lec.transcript = transcript
                            await session.commit()
                    if i % batch_size == 0:
                        await asyncio.sleep(1.5)
                except Exception as e:
                    debug_logger.log("error", f"Auto-transcript fetch failed for {lid}: {str(e)}")
                    await asyncio.sleep(2.0)

    if request.import_transcripts:
        background_tasks.add_task(fetch_playlist_transcripts, [lec.id for lec in created_lectures])

    debug_logger.log("activity", f"Imported {len(created_lectures)} videos from YouTube playlist", user_id=current_user.id)
    return {"message": f"Imported {len(created_lectures)} lectures", "count": len(created_lectures)}


@router.get("/{lecture_id}/materials", response_model=List[MaterialResponse])
async def get_lecture_materials(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Material).where(Material.lecture_id == lecture_id))
    return [MaterialResponse.model_validate(m) for m in result.scalars().all()]


@router.get("/course/{course_id}/materials", response_model=List[MaterialResponse])
async def get_course_materials(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Material).where(Material.course_id == course_id))
    return [MaterialResponse.model_validate(m) for m in result.scalars().all()]


@router.post("/materials", response_model=MaterialResponse, status_code=201)
async def add_material(
    request: Request,
    course_id: str = Form(...),
    lecture_id: Optional[str] = Form(None),
    title: str = Form(...),
    file: Optional[UploadFile] = File(None),
    file_url: Optional[str] = Form(None),
    file_type: Optional[str] = Form(None),
    file_size: int = Form(0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    if not file and not file_url:
        raise HTTPException(status_code=400, detail="Provide either file upload or file_url")

    resolved_url = file_url
    resolved_type = file_type or "application/octet-stream"
    resolved_size = file_size or 0

    if file:
        max_bytes = settings.MAX_MATERIAL_UPLOAD_MB * 1024 * 1024
        rel_path, uploaded_size = await _save_uploaded_file(file, "materials", max_bytes)
        resolved_url = _public_media_url(request, rel_path)
        resolved_type = file.content_type or resolved_type
        resolved_size = uploaded_size

    if not resolved_url:
        raise HTTPException(status_code=400, detail="Material URL could not be resolved")

    material = Material(
        course_id=course_id,
        lecture_id=lecture_id,
        title=title,
        file_url=resolved_url,
        file_type=resolved_type,
        file_size=resolved_size,
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)

    debug_logger.log("activity", f"Material added: {title}", user_id=current_user.id)
    return MaterialResponse.model_validate(material)


@router.delete("/materials/{material_id}")
async def delete_material(
    material_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    result = await db.execute(select(Material).where(Material.id == material_id))
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    await db.delete(material)
    await db.commit()
    return {"message": "Material deleted"}
@router.post("/materials/upload", response_model=MaterialResponse)
async def upload_material(
    course_id: str = Form(...),
    title: str = Form(...),
    type: str = Form("pdf"),
    lecture_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Upload a local file as a course material.
    Uses the StorageService for Cloudinary/S3/Local storage.
    """
    # 1. Verify access
    course_res = await db.execute(select(Course).where(Course.id == course_id))
    course = course_res.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # 2. Upload file
    file_url = await storage_service.upload_file(file, folder="materials")

    # 3. Save to database
    material = Material(
        id=str(uuid4()),
        course_id=course_id,
        lecture_id=lecture_id,
        title=title,
        file_url=file_url,
        file_type=type,
        created_at=datetime.utcnow(),
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)

    return material
