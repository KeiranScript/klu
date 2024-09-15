from pathlib import Path
from uuid import uuid4
from datetime import datetime
from fuzzywuzzy import process
from fastapi import FastAPI, Depends, File, UploadFile, Request, Query, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from threading import Lock
from collections import Counter
import mimetypes
import random
import json
import os

from modules.middleware import (
    verify_api_key, validate_file, handle_file_upload,
    rate_limit, RedirectOn405Middleware
)


async def lifespan(app: FastAPI):
    init_globals()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.add_middleware(RedirectOn405Middleware)


KEY_FILE = "json/keys.json"
DEL_FILE = "json/delete.json"
UPLOAD_DIR = "uploads"
BASE_URL = "https://kuuichi.xyz"

templates = Jinja2Templates(directory="templates")
file_delete_map = {}
keys = {}
file_locks = {}


def load_json(file_path: str):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)
    return {}


def save_json(file_path: str, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)


def init_globals():
    global file_delete_map, keys
    file_delete_map = load_json(DEL_FILE)
    keys = {entry['key']: entry['user'] for entry in load_json(KEY_FILE)}


def acquire_lock(file_name: str) -> Lock:
    if file_name not in file_locks:
        file_locks[file_name] = Lock()
    return file_locks[file_name]


@app.post("/")
async def upload(file: UploadFile = File(...),
                 username: str = Depends(verify_api_key)):

    lock = acquire_lock(file.filename)

    with lock:
        rate_limit(username)
        validate_file(file)
        file_path, file_size, file_type, upload_time = handle_file_upload(
            file, username, UPLOAD_DIR)

        file_url = f"{BASE_URL}/uploads/{username}/{file_path.name}"
        delete_uuid = str(uuid4())
        delete_url = f"{BASE_URL}/delete/{delete_uuid}"

        file_delete_map[delete_uuid] = str(file_path.resolve())
        save_json(DEL_FILE, file_delete_map)

        return JSONResponse(content={
            "file_url": file_url,
            "file-size": format_file_size(file_size),
            "file-type": file_type,
            "date-uploaded": upload_time,
            "delete_url": delete_url
        })


def format_file_size(size_in_bytes: int) -> str:
    if size_in_bytes >= 1024**2:
        return f"{size_in_bytes / 1024**2:.2f} MB"
    return f"{size_in_bytes / 1024:.2f} KB"


@app.get("/delete/{delete_uuid}")
async def delete_file(request: Request, delete_uuid: str):
    file_path = file_delete_map.pop(delete_uuid, None)

    if file_path:
        save_json(DEL_FILE, file_delete_map)

    if not file_path or not os.path.exists(file_path):
        return templates.TemplateResponse("file_not_found.html", {"request": request})

    os.remove(file_path)
    return templates.TemplateResponse("file_deleted.html", {"request": request})


@app.get("/files")
async def list_files(username: str = Depends(verify_api_key)):
    user_dir = Path(UPLOAD_DIR) / username

    if not user_dir.exists():
        return JSONResponse(content={"error": "User directory not found"}, status_code=404)

    files = [
        {
            "file_name": file_name,
            "file_url": f"{BASE_URL}/uploads/{username}/{file_name}",
            "file-size": format_file_size(file.stat().st_size),
            "file-type": file_name.split('.')[-1] if '.' in file_name else "unknown",
            "date-uploaded": datetime.fromtimestamp(file.stat().st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
            "delete_url": f"{BASE_URL}/delete/{next((key for key, value in file_delete_map.items() if value == str(file.resolve())), 'N/A')}"
        }
        for file_name in os.listdir(user_dir)
        if (file := user_dir / file_name).is_file()
    ]

    return JSONResponse(content={"files": files})


@app.get("/search")
async def search_files(query: str, username: str = Depends(verify_api_key)):
    user_dir = Path(UPLOAD_DIR) / username
    if not user_dir.exists():
        return JSONResponse(content={"error": "User directory not found"}, status_code=404)

    file_names = [f.name for f in user_dir.glob("*") if f.is_file()]
    matches = process.extract(query, file_names, limit=10)

    results = [
        {"file_name": match, "file_url": f"{
            BASE_URL}/uploads/{username}/{match}", "score": score}
        for match, score in matches
    ]

    return JSONResponse(content={"results": results})


@app.get("/lol")
async def get_image(request: Request):
    query = list(request.query_params.keys())[
        0] if request.query_params else None
    image_dir = Path("static/images")
    image_files = list(image_dir.glob("*.*"))

    if not image_files:
        return JSONResponse(content={"error": "No images found"}, status_code=404)

    specific_file = None

    if query:
        file_names = [file.name for file in image_files]
        closest_match, _ = process.extractOne(query, file_names)
        if closest_match:
            specific_file = image_dir / closest_match

    selected_image = specific_file if specific_file else random.choice(
        image_files)
    mime_type, _ = mimetypes.guess_type(selected_image)
    mime_type = mime_type or "application/octet-stream"

    headers = {
        "Content-Type": mime_type,
        "Content-Disposition": "inline"
    }

    return FileResponse(path=selected_image, headers=headers)


@app.get("/info")
async def get_server_info():
    upload_dir = Path(UPLOAD_DIR)
    total_storage_used = sum(
        f.stat().st_size for f in upload_dir.glob('**/*') if f.is_file())
    total_uploads = sum(1 for f in upload_dir.glob('**/*') if f.is_file())
    total_users = sum(1 for d in upload_dir.iterdir() if d.is_dir())

    return JSONResponse(content={
        "storage_used": format_size(total_storage_used),
        "uploads": total_uploads,
        "users": total_users
    })


@app.get("/analytics")
async def get_analytics():
    upload_files = [f for f in Path(UPLOAD_DIR).glob('**/*') if f.is_file()]
    file_types = Counter(f.suffix for f in upload_files)
    user_uploads = Counter(f.parent.name for f in upload_files)

    return JSONResponse(content={
        "file_types": dict(file_types),
        "user_uploads": dict(user_uploads)
    })


def format_size(size_in_bytes: int) -> str:
    if size_in_bytes >= 1024**3:
        return f"{size_in_bytes / 1024**3:.2f} GB"
    if size_in_bytes >= 1024**2:
        return f"{size_in_bytes / 1024**2:.2f} MB"
    if size_in_bytes >= 1024:
        return f"{size_in_bytes / 1024:.2f} KB"
    return f"{size_in_bytes} B"


@app.get("/file_info")
async def get_file_info(filename: str, username: str = Depends(verify_api_key)):
    user_dir = Path(UPLOAD_DIR) / username

    if not user_dir.exists():
        raise HTTPException(status_code=404, detail="User directory not found")

    file_path = user_dir / filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    file_size = file_path.stat().st_size
    file_type = filename.split('.')[-1] if '.' in filename else "unknown"
    upload_time = datetime.fromtimestamp(
        file_path.stat().st_ctime).strftime('%Y-%m-%d %H:%M:%S')

    delete_uuid = next((key for key, value in file_delete_map.items(
    ) if value == str(file_path.resolve())), None)
    delete_url = f"{BASE_URL}/delete/{delete_uuid}" if delete_uuid else "N/A"

    return JSONResponse(content={
        "file_name": filename,
        "file_url": f"{BASE_URL}/uploads/{username}/{filename}",
        "file-size": f"{file_size / 1024**2:.2f} MB" if file_size >= 1024**2 else f"{file_size / 1024:.2f} KB",
        "file-type": file_type,
        "date-uploaded": upload_time,
        "delete_url": delete_url
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
