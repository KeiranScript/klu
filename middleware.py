import json
import time
from fastapi import HTTPException, status, UploadFile
from pathlib import Path
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta

# Constants
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png",
                      "pdf", "txt", "doc",
                      "docx", "xls", "xlsx",
                      "gif", "webp", "mp4",
                      "mp3", "avi", "mkv",
                      "zip", "rar", "7z",
                      "iso", "bin", "dmg",
                      "apk", "deb", "rpm"
                      "tar", "gz", "xz",
                      "bz2", "zst", "lz4"
                      }
RATE_LIMIT = 5  # Max number of requests
RATE_LIMIT_TIME = timedelta(minutes=1)  # Time window for rate limiting
KEY_FILE = "keys.json"

# Rate limiter dictionary
rate_limiter = defaultdict(list)


def load_api_keys():
    with open(KEY_FILE, 'r') as file:
        data = json.load(file)
    return {entry['key']: entry['user'] for entry in data}


keys = load_api_keys()


def verify_api_key(api_key: str):
    if api_key in keys:
        return keys[api_key]
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key"
    )


def rate_limit(api_key: str):
    current_time = datetime.now()
    access_times = rate_limiter[api_key]

    # Filter access times within the rate limit time window
    rate_limiter[api_key] = [t for t in access_times if t >
                             current_time - RATE_LIMIT_TIME]

    if len(rate_limiter[api_key]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later."
        )

    rate_limiter[api_key].append(current_time)


def validate_file(file: UploadFile):
    file_extension = file.filename.split('.')[-1].lower()

    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {
                ', '.join(ALLOWED_EXTENSIONS)}"
        )

    file_content = file.file.read()
    file_size = len(file_content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 100MB limit."
        )

    if b'<?php' in file_content or b'<script>' in file_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File may contain malicious content."
        )

    file.file.seek(0)  # Reset file pointer after reading

    return True


def handle_file_upload(file: UploadFile, username: str, upload_dir: str):
    file_extension = file.filename.split('.')[-1]
    random_filename = hashlib.sha256(str(time.time()).encode()).hexdigest()[
        :8] + f".{file_extension}"

    user_dir = Path(upload_dir) / username
    user_dir.mkdir(parents=True, exist_ok=True)

    file_path = user_dir / random_filename
    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())

    file_size = file_path.stat().st_size
    upload_time = time.strftime("%d-%m-%Y %H:%M", time.localtime())

    return file_path, file_size, file.content_type.split("/")[-1], upload_time
