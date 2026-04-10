"""
Smart LMS - Storage Service
Abstracts file storage (Cloudinary, Local, and future AWS S3)
"""

import os
import shutil
from uuid import uuid4
from typing import Optional
from fastapi import UploadFile
import boto3
from botocore.exceptions import ClientError
from app.config import settings
from app.services.debug_logger import debug_logger

class StorageService:
    def __init__(self):
        self.provider = settings.STORAGE_PROVIDER # 'cloudinary', 's3', or 'local'
        
        # Configure Cloudinary if credentials exist
        self.has_cloudinary = False
        if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
            try:
                import cloudinary
                import cloudinary.uploader
                cloudinary.config(
                    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
                    api_key=settings.CLOUDINARY_API_KEY,
                    api_secret=settings.CLOUDINARY_API_SECRET,
                    secure=True
                )
                self.has_cloudinary = True
            except Exception as e:
                debug_logger.log("storage", f"Cloudinary Initialization Failed: {e}")

        # Configure AWS S3 if credentials exist
        self.s3_client = None
        self.bucket_name = settings.AWS_S3_BUCKET or settings.AWS_S3_MODEL_BUCKET

        if self.bucket_name:
            try:
                # Initialize with keys if present, otherwise rely on IAM Role
                s3_args = {'region_name': settings.AWS_REGION}
                if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                    s3_args.update({
                        'aws_access_key_id': settings.AWS_ACCESS_KEY_ID,
                        'aws_secret_access_key': settings.AWS_SECRET_ACCESS_KEY
                    })
                
                self.s3_client = boto3.client('s3', **s3_args)
                self.has_s3 = True
                print(f"[STORAGE] AWS S3 initialized using bucket: {self.bucket_name} (Mode: {'IAM Role' if not settings.AWS_ACCESS_KEY_ID else 'Access Keys'})", flush=True)
                print(f"[STORAGE] AWS S3 initialized using bucket: {self.bucket_name}", flush=True)
            except Exception as e:
                debug_logger.log("storage", f"S3 Initialization Failed: {e}")

    async def upload_file(self, file: UploadFile, folder: str = "materials") -> str:
        """
        Uploads a file to the configured storage provider.
        Returns the public URL of the uploaded file.
        """
        filename = f"{uuid4()}_{file.filename}"
        
        # --- Primary: Cloudinary ---
        if self.has_cloudinary:
            try:
                import cloudinary.uploader
                content = await file.read()
                upload_result = cloudinary.uploader.upload(
                    content,
                    folder=f"smartlms/{folder}",
                    resource_type="auto"
                )
                await file.seek(0)
                return upload_result.get("secure_url")
            except Exception as e:
                debug_logger.log("storage", f"Cloudinary failed, falling back: {e}")
                await file.seek(0)

        # --- Secondary: AWS S3 ---
        if self.has_s3 and self.s3_client:
            try:
                s3_key = f"{folder}/{filename}"
                self.s3_client.upload_fileobj(
                    file.file,
                    self.bucket_name,
                    s3_key,
                    ExtraArgs={'ACL': 'public-read'} # As per user request (public read)
                )
                return f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
            except Exception as e:
                debug_logger.log("storage", f"S3 failed, falling back: {e}")
                await file.seek(0)

        # --- Tertiary: Local Storage (Absolute Safety) ---
        upload_dir = os.path.join(settings.UPLOAD_DIR, folder)
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Return relative path for serving via app.mount("/media", ...)
        return f"{settings.API_BASE_URL}/media/{folder}/{filename}"

storage_service = StorageService()
