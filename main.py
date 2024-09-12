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
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")


def handle_file_upload(file: UploadFile, username: str):
    file_extension = file.filename.split('.')[-1]
    random_filename = ''.join(random.choices(
        string.ascii_letters + string.digits, k=8)) + f".{file_extension}"
    user_dir = Path(base_upload_dir) / username
    user_dir.mkdir(parents=True, exist_ok=True)
    file_path = user_dir / random_filename
    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())
    file_size = file_path.stat().st_size
    upload_time = time.strftime("%d-%m-%Y %H:%M", time.localtime())
    return file_path, file_size, file.content_type.split("/")[-1], upload_time


@app.post("/")
async def upload(file: UploadFile = File(...), username: str = Depends(verify_api_key)):
    file_path, file_size, file_type, upload_time = handle_file_upload(
        file, username)
    file_url = f"{base_url}/{file_path}"
    return JSONResponse(content={
        "file_url": file_url,
        "file-size": f"{file_size / 1024**2:.2f} MB" if file_size >= 1024**2 else f"{file_size / 1024:.2f} KB",
        "file-type": file_type,
        "date-uploaded": upload_time
    })
