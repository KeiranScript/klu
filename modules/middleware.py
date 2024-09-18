import json
import time
import shutil
import os
from fastapi import HTTPException, Header, status, UploadFile
from pathlib import Path
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 104857600))  # Default to 100MB if not set
RATE_LIMIT = int(os.getenv("RATE_LIMIT", 30))
RATE_LIMIT_TIME = timedelta(seconds=int(os.getenv("RATE_LIMIT_TIME", 60)))
KEY_FILE = os.getenv("KEY_FILE", "json/keys.json")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

rate_limiter = defaultdict(list)


def load_api_keys():
    with open(KEY_FILE, 'r') as file:
        data = json.load(file)
    return {entry['key']: entry['user'] for entry in data}


keys = load_api_keys()


def rate_limit(username: str):
    current_time = datetime.now()
    access_times = rate_limiter[username]

    rate_limiter[username] = [t for t in access_times if t >
                              current_time - RATE_LIMIT_TIME]

    if len(rate_limiter[username]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later."
        )

    rate_limiter[username].append(current_time)


def validate_file(file: UploadFile):
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds {MAX_FILE_SIZE / (1024 * 1024):.2f}MB limit."
        )

    content_sample = file.file.read(1024)
    file.file.seek(0)

    if b'<?php' in content_sample or b'<script>' in content_sample:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File may contain malicious content."
        )

    return True


def handle_file_upload(file: UploadFile, username: str, upload_dir: str = UPLOAD_DIR):
    file_extension = Path(file.filename).suffix.lower()

    random_filename = hashlib.sha256(str(time.time()).encode()).hexdigest()[:8] + file_extension

    user_dir = Path(upload_dir) / username
    user_dir.mkdir(parents=True, exist_ok=True)

    file_path = user_dir / random_filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = file_path.stat().st_size
    upload_time = datetime.now().strftime("%d-%m-%Y %H:%M")

    return file_path, file_size, file.content_type.split("/")[-1], upload_time
