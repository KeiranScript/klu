import json
import time
import random
import string
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI()

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

api_keys_file = "keys.json"
base_upload_dir = "uploads"
base_url = "http://localhost:8000"


def load_api_keys():
    with open(api_keys_file, 'r') as file:
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


def get_filesize(file_path: Path):
    in_bytes = file_path.stat().st_size

    if in_bytes >= 1024:
        in_kb = in_bytes / 1024
        if in_kb >= 1024:
            in_mb = in_kb / 1024
            if in_mb >= 1024:
                in_gb = in_mb / 1024
                return f"{in_gb:.2f} GB"
            return f"{in_mb:.2f} MB"
        return f"{in_kb:.2f} KB"


def generate_random_filename(extension: str):
    random_str = ''.join(random.choices(
        string.ascii_letters + string.digits, k=8))
    return f"{random_str}.{extension}"


def save_uploaded_file(file: UploadFile, username: str):
    file_extension = file.filename.split('.')[-1]
    random_filename = generate_random_filename(file_extension)

    user_dir = Path(base_upload_dir) / username
    user_dir.mkdir(parents=True, exist_ok=True)

    file_path = user_dir / random_filename

    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())

    upload_time = time.strftime("%d-%m-%Y %H:%M", time.localtime())

    return file_path, upload_time


@app.post("/")
async def upload(file: UploadFile = File(...),
                 username: str = Depends(verify_api_key)):
    file_path, upload_time = save_uploaded_file(file, username)
    file_url = base_url + "/" + str(file_path)

    return JSONResponse(content={
        "file_url": file_url,
        "file-size: ": get_filesize(file_path),
        "file-type": file.content_type.split("/")[-1],
        "date-uploaded": upload_time
    })
