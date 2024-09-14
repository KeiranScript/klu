from modules.middleware import (verify_api_key, validate_file,
                                handle_file_upload, rate_limit,
                                RedirectOn405Middleware)

from pathlib import Path
from uuid import uuid4
from datetime import datetime
from fuzzywuzzy import process
from fastapi import FastAPI, Depends, File, UploadFile, Request, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import mimetypes
import random
import json
import os

app = FastAPI()

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.add_middleware(RedirectOn405Middleware)

KEY_FILE = "json/keys.json"
DEL_FILE = "json/delete.json"
UPLOAD_DIR = "uploads"
BASE_URL = "https://kuuichi.xyz"


def load_api_keys():
    with open(KEY_FILE, 'r') as file:
        data = json.load(file)
    return {entry['key']: entry['user'] for entry in data}


def load_delete_map():
    if os.path.exists(DEL_FILE):
        with open(DEL_FILE, 'r') as file:
            return json.load(file)
    return {}


def save_delete_map(delete_map):
    with open(DEL_FILE, 'w') as file:
        json.dump(delete_map, file, indent=4)


templates = Jinja2Templates(directory="templates")
file_delete_map = load_delete_map()
keys = load_api_keys()


@app.post("/")
async def upload(file: UploadFile = File(...),
                 username: str = Depends(verify_api_key)):
    rate_limit(username)
    validate_file(file)
    file_path, file_size, file_type, upload_time = handle_file_upload(
        file, username, UPLOAD_DIR)

    file_url = f"{BASE_URL}/uploads/{username}/{file_path.name}"

    delete_uuid = str(uuid4())
    delete_url = f"{BASE_URL}/delete/{delete_uuid}"

    file_path_str = str(file_path.resolve())
    file_delete_map[delete_uuid] = file_path_str
    save_delete_map(file_delete_map)

    # Debug logging
    print(f"DEBUG: Uploaded file {file_path.name} with delete_uuid: {
          delete_uuid}, file_path: {file_path_str}")

    return JSONResponse(content={
        "file_url": file_url,
        "file-size": f"{file_size / 1024**2:.2f} MB" if file_size >= 1024**2
        else f"{file_size / 1024:.2f} KB",
        "file-type": file_type,
        "date-uploaded": upload_time,
        "delete_url": delete_url
    })


@app.get("/delete/{delete_uuid}")
async def delete_file(request: Request, delete_uuid: str):
    file_path = file_delete_map.pop(delete_uuid, None)

    if file_path:
        save_delete_map(file_delete_map)

    if not file_path or not os.path.exists(file_path):
        return templates.TemplateResponse("file_not_found.html",
                                          {"request": request})

    os.remove(file_path)
    return templates.TemplateResponse("file_deleted.html",
                                      {"request": request})


@app.get("/files")
async def list_files(username: str = Depends(verify_api_key)):
    user_dir = Path(UPLOAD_DIR) / username

    if not user_dir.exists():
        return JSONResponse(content={"error": "User directory not found"}, status_code=404)

    files = []

    for file_name in os.listdir(user_dir):
        file_path = user_dir / file_name
        file_path_str = str(file_path.resolve())  # Ensure absolute path
        filesize = file_path.stat().st_size
        upload_time = datetime.fromtimestamp(
            file_path.stat().st_ctime).strftime('%Y-%m-%d %H:%M:%S')
        file_type = file_name.split('.')[-1] if '.' in file_name else "unknown"

        delete_uuid = next(
            (key for key, value in file_delete_map.items() if value == file_path_str), None)

        delete_url = f"{
            BASE_URL}/delete/{delete_uuid}" if delete_uuid else "N/A"

        # Debug logging
        print(f"DEBUG: Listing file {file_name} with file_path_str: {
              file_path_str}, delete_uuid: {delete_uuid}, delete_url: {delete_url}")

        files.append({
            "file_name": file_name,
            "file_url": f"{BASE_URL}/uploads/{username}/{file_name}",
            "file-size": f"{filesize / 1024**2:.2f} MB" if filesize >= 1024**2 else f"{filesize / 1024:.2f} KB",
            "file-type": file_type,
            "date-uploaded": upload_time,
            "delete_url": delete_url
        })

    return JSONResponse(content={"files": files})


@app.get("/lol")
async def get_image(file_name: str = Query(None,
                                           alias="file",
                                           description="\
                                           Name of the file to retrieve")):
    image_dir = Path("static/images")
    image_files = list(image_dir.glob("*.*"))

    if not image_files:
        return JSONResponse(content={"error": "No images found"},
                            status_code=404)

    specific_file = None

    if file_name:
        file_names = [file.name for file in image_files]
        closest_match, _ = process.extractOne(file_name, file_names)

        if closest_match:
            specific_file = image_dir / closest_match
            if specific_file in image_files:
                image_files = [specific_file]
            else:
                specific_file = None

    selected_image = specific_file if specific_file else random.choice(
        image_files)

    mime_type, _ = mimetypes.guess_type(selected_image)
    if mime_type is None:
        mime_type = "application/octet-stream"

    return FileResponse(path=selected_image,
                        headers={"Content-Type": mime_type})


@app.get("/info")
async def get_server_info():
    upload_dir = Path(UPLOAD_DIR)
    total_storage_used = sum(
        f.stat().st_size for f in upload_dir.glob('**/*') if f.is_file())
    total_uploads = sum(1 for f in upload_dir.glob('**/*') if f.is_file())
    total_users = sum(1 for d in upload_dir.iterdir() if d.is_dir())

    def format_size(size_in_bytes):
        if size_in_bytes >= 1024 ** 3:
            return f"{size_in_bytes / (1024 ** 3):.2f} GB"
        elif size_in_bytes >= 1024 ** 2:
            return f"{size_in_bytes / (1024 ** 2):.2f} MB"
        elif size_in_bytes >= 1024:
            return f"{size_in_bytes / 1024:.2f} KB"
        return f"{size_in_bytes} B"

    return JSONResponse(content={
        "storage_used": format_size(total_storage_used),
        "uploads": total_uploads,
        "users": total_users
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
