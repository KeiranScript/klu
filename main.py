from middleware import (verify_api_key, validate_file,
                        handle_file_upload, rate_limit,
                        RedirectOn405Middleware)

from pathlib import Path
from uuid import uuid4
import json
import os
from datetime import datetime
from fastapi import FastAPI, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.add_middleware(RedirectOn405Middleware)

KEY_FILE = "keys.json"
UPLOAD_DIR = "uploads"
BASE_URL = "https://kuuichi.xyz"

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

file_delete_map = {}


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

    file_url = f"{BASE_URL}/uploads/{username}/{file_path.name}"

    # Generate UUID and map it to the file path
    delete_uuid = str(uuid4())
    delete_url = f"{BASE_URL}/delete/{delete_uuid}"
    file_delete_map[delete_uuid] = file_path

    return JSONResponse(content={
        "file_url": file_url,
        "file-size": f"{file_size / 1024**2:.2f} MB" if file_size >= 1024**2
        else f"{file_size / 1024:.2f} KB",
        "file-type": file_type,
        "date-uploaded": upload_time,
        "delete_url": delete_url  # Include the delete URL in the response
    })


@app.get("/delete/{delete_uuid}")
async def delete_file(delete_uuid: str):
    # Find the file path from the UUID
    file_path = file_delete_map.pop(delete_uuid, None)

    if not file_path or not os.path.exists(file_path):
        return JSONResponse(content={"error": "File not found"}, status_code=404)

    # Delete the file
    os.remove(file_path)

    return JSONResponse(content={"message": "File deleted successfully"})


@app.get("/files")
async def list_files(username: str = Depends(verify_api_key)):
    user_dir = Path(UPLOAD_DIR) / username

    if not user_dir.exists():
        return JSONResponse(content={"error": "User directory not found"}, status_code=404)

    files = []

    for file_name in os.listdir(user_dir):
        file_path = user_dir / file_name
        filesize = file_path.stat().st_size
        upload_time = datetime.fromtimestamp(
            file_path.stat().st_ctime).strftime('%Y-%m-%d %H:%M:%S')
        file_type = file_name.split('.')[-1] if '.' in file_name else "unknown"

        files.append({
            "file_name": file_name,
            "file_url": f"{BASE_URL}/uploads/{username}/{file_name}",
            "file-size": f"{filesize / 1024**2:.2f} MB" if filesize >= 1024**2 else f"{filesize / 1024:.2f} KB",
            "file-type": file_type,
            "date-uploaded": upload_time
        })

    return JSONResponse(content={"files": files})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
