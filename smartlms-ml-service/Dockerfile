# ==========================================
# STAGE 1: Builder (The 8GB "Ghost")
# ==========================================
FROM python:3.10-slim as builder

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH /app

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Heavy Libraries for Conversion
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir tf2onnx onnxruntime

# Copy code for conversion
COPY app/ app/
COPY export/ export/

# RUN THE CONVERSION
# RUN python app/ml/convert_to_onnx.py

# PRUNE: Delete original heavy models (.h5, .pt) to save space before copying
RUN find export/ -name "*.h5" -delete && \
    find export/ -name "*.pt" -delete && \
    find export/ -name "__pycache__" -type d -exec rm -rf {} +

# ==========================================
# STAGE 2: Runtime (The <1GB "Lean" image)
# ==========================================
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH /app

WORKDIR /app

# Install only minimal runtime system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install ONLY the essential runtime libraries (Removed pandas, scikit-learn, etc. to reach < 1GB)
RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn==0.27.0 \
    pydantic-settings==2.1.0 \
    onnxruntime==1.17.1 \
    numpy==1.26.3 \
    xgboost==2.0.3 \
    joblib==1.3.2 \
    opencv-python-headless==4.9.0.80 \
    boto3==1.34.34 \
    sqlalchemy==2.0.25 \
    asyncpg==0.29.0 \
    greenlet==3.0.3

# Copy Application Code
COPY app/ app/

# NOTE: The 'export/' folder is NOT copied here to keep the image size low.
# Models will be downloaded from S3 (Lazy Loading) on first use.
# To populate S3, use: aws s3 sync ./export/ s3://[BUCKET]/models/

# Expose port (API mode)
EXPOSE 8001

# Default: Run the API.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--log-level", "info"]
