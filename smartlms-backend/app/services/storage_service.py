"""
Smart LMS - Storage Service
Abstracts file storage (S3 Priority, Cloudinary, and Local)
"""

import os
import shutil
import io
from uuid import uuid4
from typing import Optional
from fastapi import UploadFile
import boto3
from botocore.exceptions import ClientError
from app.config import settings
from app.services.debug_logger import debug_logger

class StorageService:
    def __init__(self):
        self.provider = settings.STORAGE_PROVIDER # Default: 's3'
        
        # Configure AWS S3
        self.s3_client = None
        self.bucket_name = settings.AWS_S3_BUCKET or settings.AWS_S3_MODEL_BUCKET
        self.has_s3 = False

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
                print(f"[STORAGE] AWS S3 initialized using bucket: {self.bucket_name}", flush=True)
            except Exception as e:
                debug_logger.log("storage", f"S3 Initialization Failed: {e}")

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

    async def upload_file(self, file: UploadFile, folder: str = "materials") -> str:
        """
        Uploads a file to the configured storage provider.
        Priority: S3 -> Cloudinary -> Local
        Returns the public/accessible URL of the uploaded file.
        """
        filename = f"{uuid4()}_{file.filename}"
        
        # --- Primary: AWS S3 ---
        if self.has_s3 and self.s3_client:
            try:
                s3_key = f"{folder}/{filename}"
                self.s3_client.upload_fileobj(
                    file.file,
                    self.bucket_name,
                    s3_key,
                    ExtraArgs={'ACL': 'public-read'} # Defaulting to public-read for materials
                )
                await file.seek(0)
                # Note: For production with private buckets, use generate_presigned_url instead
                return f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
            except Exception as e:
                debug_logger.log("storage", f"S3 upload failed: {e}")
                await file.seek(0)

        # --- Secondary: Cloudinary ---
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
                debug_logger.log("storage", f"Cloudinary failed: {e}")
                await file.seek(0)

        # --- Tertiary: Local Storage (Absolute Safety) ---
        upload_dir = os.path.join(settings.UPLOAD_DIR, folder)
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return f"{settings.API_BASE_URL}/media/{folder}/{filename}"

    def generate_presigned_url(self, s3_url: str, expiration: int = 3600) -> Optional[str]:
        """
        Generates a temporary presigned URL for a private S3 object.
        Used for rendering student PDFs securely in the HUD.
        """
        if not self.has_s3 or not self.s3_client:
            return s3_url # Fallback to literal URL
            
        try:
            # Extract key from URL
            # Format: https://bucket.s3.region.amazonaws.com/folder/file
            if "amazonaws.com/" in s3_url:
                s3_key = s3_url.split("amazonaws.com/")[-1]
                
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': s3_key},
                    ExpiresIn=expiration
                )
                return url
        except Exception as e:
            debug_logger.log("storage", f"Presigned URL generation failed: {e}")
        
        return s3_url

    async def get_file_as_bytes(self, url: str) -> Optional[bytes]:
        """
        Retrieves file content as bytes for local processing (e.g. AI PDF Parsing).
        """
        # Case 1: S3
        if self.has_s3 and self.s3_client and "amazonaws.com/" in url:
            try:
                s3_key = url.split("amazonaws.com/")[-1]
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
                return response['Body'].read()
            except Exception as e:
                debug_logger.log("storage", f"S3 download failed: {e}")

        # Case 2: Local File
        if f"{settings.API_BASE_URL}/media/" in url:
            try:
                relative_path = url.split("/media/")[-1]
                local_path = os.path.join(settings.UPLOAD_DIR, relative_path)
                if os.path.exists(local_path):
                    with open(local_path, "rb") as f:
                        return f.read()
            except Exception as e:
                debug_logger.log("storage", f"Local read failed: {e}")

        # Case 3: Remote fallback (Cloudinary/Web)
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.content
        except Exception as e:
            debug_logger.log("storage", f"Remote download failed: {e}")
            
        return None

storage_service = StorageService()
