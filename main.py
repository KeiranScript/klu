from middleware import (verify_api_key, validate_file,
                        handle_file_upload, rate_limit)

import json
from fastapi import FastAPI, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

KEY_FILE = "keys.json"
UPLOAD_DIR = "uploads"
BASE_URL = "http://localhost:8000"

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png",
                      "pdf", "txt", "doc",
                      "docx", "xls", "xlsx"}


def load_api_keys():
    with open(KEY_FILE, 'r') as file:
        data = json.load(file)
    return {entry['key']: entry['user'] for entry in data}


keys = load_api_keys()


@app.post("/")
async def upload(file: UploadFile = File(...),
                 username: str = Depends(verify_api_key)):
    rate_limit(username)
    validate_file(file)
    file_path, file_size, file_type, upload_time = handle_file_upload(
        file, username, UPLOAD_DIR)
    file_url = f"{BASE_URL}/{file_path}"

    return JSONResponse(content={
        "file_url": file_url,
        "file-size": f"{file_size / 1024**2:.2f} MB" if file_size >= 1024**2
        else f"{file_size / 1024:.2f} KB",
        "file-type": file_type,
        "date-uploaded": upload_time
    })
