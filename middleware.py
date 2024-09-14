import json
import time
from fastapi import HTTPException, Header, status, UploadFile
from pathlib import Path
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import RedirectResponse

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
RATE_LIMIT = 5
RATE_LIMIT_TIME = timedelta(minutes=1)
KEY_FILE = "keys.json"

rate_limiter = defaultdict(list)


def load_api_keys():
    with open(KEY_FILE, 'r') as file:
        data = json.load(file)
    return {entry['key']: entry['user'] for entry in data}


keys = load_api_keys()


def verify_api_key(authorization: str = Header(None)):
    if not authorization or authorization not in keys:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return keys[authorization]


def rate_limit(api_key: str):
    current_time = datetime.now()
    access_times = rate_limiter[api_key]

    rate_limiter[api_key] = [t for t in access_times if t >
                             current_time - RATE_LIMIT_TIME]

    if len(rate_limiter[api_key]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later."
        )

    rate_limiter[api_key].append(current_time)


def validate_file(file: UploadFile):
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
    user_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists

    file_path = user_dir / random_filename
    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())

    file_size = file_path.stat().st_size
    upload_time = time.strftime("%d-%m-%Y %H:%M", time.localtime())

    return file_path, file_size, file.content_type.split("/")[-1], upload_time


class RedirectOn405Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if response.status_code == 405:
            return RedirectResponse(url="/docs")
        return response
