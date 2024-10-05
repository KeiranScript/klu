import mimetypes
from fastapi import FastAPI, Depends, File, UploadFile, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from rapidfuzz import process
from threading import Lock
from pathlib import Path
from uuid import uuid4

import string
import random
import json
import os
import shutil

from modules.middleware import validate_file, handle_file_upload, rate_limit

app = FastAPI()

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount(
    "/bio_files", StaticFiles(directory="static/bio_files", html=True), name="static"
)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
DEL_FILE = os.getenv("DEL_FILE", "json/delete.json")
KEY_FILE = os.getenv("KEY_FILE", "json/keys.json")
SRV_FILE = "json/srv.json"
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

templates = Jinja2Templates(directory="templates")
file_delete_map = {}
file_name_map = {}
keys = {}
file_locks = {}


def load_json(file_path: str):
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Error decoding JSON file")


def save_json(file_path: str, data):
    try:
        with open(file_path, "w") as file:
            json.dump(data, file, indent=4)
    except IOError:
        raise HTTPException(
            status_code=500, detail="Error writing to JSON file")


def load_files_json(file_path: str):
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Error decoding JSON file")


def save_files_json(file_path: str, data):
    try:
        with open(file_path, "w") as file:
            json.dump(data, file, indent=4)
    except IOError:
        raise HTTPException(
            status_code=500, detail="Error writing to JSON file")


def init_globals():
    global file_delete_map, keys
    file_delete_map = load_json(DEL_FILE)
    keys = {entry["key"]: entry["user"] for entry in load_json(KEY_FILE)}


def acquire_lock(file_name: str) -> Lock:
    if file_name not in file_locks:
        file_locks[file_name] = Lock()
    return file_locks[file_name]


def format_file_size(size_in_bytes: int) -> str:
    return (
        f"{size_in_bytes / 1024**2:.2f} MB"
        if size_in_bytes >= 1024**2
        else f"{size_in_bytes / 1024:.2f} KB"
    )


def format_size(size_in_bytes: int) -> str:
    if size_in_bytes >= 1024**3:
        return f"{size_in_bytes / 1024**3:.2f} GB"
    if size_in_bytes >= 1024**2:
        return f"{size_in_bytes / 1024**2:.2f} MB"
    if size_in_bytes >= 1024:
        return f"{size_in_bytes / 1024:.2f} KB"
    return f"{size_in_bytes} B"


def generate_random_filename(length=8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


init_globals()


async def verify_api_key(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="No API key provided")

    if authorization.startswith("Bearer "):
        authorization = authorization.split(" ")[1]

    if authorization not in keys:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return keys[authorization]


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/login")
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/mydocs")
async def mydocs(request: Request):
    return templates.TemplateResponse("docs.html", {"request": request})


@app.get("/bio")
async def bio(request: Request):
    return templates.TemplateResponse("bio.html", {"request": request})


@app.get("/stats")
async def stats(request: Request):
    return templates.TemplateResponse("stats.html", {"request": request})


@app.get("/info")
async def get_server_info():
    upload_dir = Path(UPLOAD_DIR)
    total_storage_used = sum(
        f.stat().st_size for f in upload_dir.glob("**/*") if f.is_file()
    )
    total_uploads = sum(1 for _ in upload_dir.glob("**/*") if _.is_file())
    total_users = sum(1 for _ in upload_dir.iterdir() if _.is_dir())

    return JSONResponse(
        content={
            "storage_used": format_size(total_storage_used),
            "uploads": total_uploads,
            "users": total_users,
        }
    )


@app.post("/upload")
async def upload(file: UploadFile = File(...), username: str = Depends(verify_api_key)):
    with acquire_lock(file.filename):
        rate_limit(username)
        validate_file(file)
        file_path, file_size, file_type, upload_time = handle_file_upload(
            file, username, UPLOAD_DIR
        )
        generated_name = generate_random_filename()
        full_file_path = (
            Path(UPLOAD_DIR) / username / f"{generated_name}{file_path.suffix}"
        )

        try:
            shutil.move(str(file_path), str(full_file_path))
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error moving file: {str(e)}")

        if not full_file_path.exists():
            raise HTTPException(
                status_code=500, detail="File could not be found after upload"
            )

        file_name_map[generated_name] = str(full_file_path)
        delete_uuid = str(uuid4())
        file_delete_map[delete_uuid] = str(full_file_path)
        save_json(DEL_FILE, file_delete_map)

        # Save generated filename to files.json
        files_data = load_files_json(SRV_FILE)
        files_data.append(
            {
                "generated_name": generated_name,
                "original_filename": file.filename,
                "username": username,
                "file_size": format_file_size(file_size),
                "file_type": file_type,
                "date_uploaded": upload_time,
                "file_url": f"{BASE_URL}/{generated_name}{file_path.suffix}",
                "delete_url": f"{BASE_URL}/delete/{delete_uuid}",
            }
        )
        save_files_json(SRV_FILE, files_data)

        return JSONResponse(
            content={
                "file_url": f"{BASE_URL}/{generated_name}{full_file_path.suffix}",
                "file-size": format_file_size(file_size),
                "file-type": file_type,
                "date-uploaded": upload_time,
                "delete_url": f"{BASE_URL}/delete/{delete_uuid}",
            }
        )


@app.get("/delete/{delete_uuid}")
async def delete_file(request: Request, delete_uuid: str):
    file_path = file_delete_map.pop(delete_uuid, None)
    save_json(DEL_FILE, file_delete_map)

    if not file_path or not os.path.exists(file_path):
        return templates.TemplateResponse("file_not_found.html", {"request": request})

    try:
        os.remove(file_path)
    except OSError as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete file: {str(e)}")

    return templates.TemplateResponse("file_deleted.html", {"request": request})


@app.get("/files")
async def list_files(username: str = Depends(verify_api_key)):
    user_dir = Path(UPLOAD_DIR) / username
    if not user_dir.exists():
        raise HTTPException(status_code=404, detail="User directory not found")

    files = [
        {
            "file_name": file.name,
            "file_url": f"{BASE_URL}/uploads/{username}/{file.name}",
            "file-size": format_file_size(file.stat().st_size),
            "file-type": file.suffix[1:] if file.suffix else "unknown",
            "date-uploaded": datetime.fromtimestamp(file.stat().st_ctime).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "delete_url": f"{BASE_URL}/delete/{next((key for key, value in file_delete_map.items() if value == str(file.resolve())), 'N/A')}",
        }
        for file in user_dir.glob("*")
        if file.is_file()
    ]

    return JSONResponse(content={"files": files})


@app.get("/search")
async def search_files(
    query: str, username: str = Depends(verify_api_key), limit: int = 10
):
    user_dir = Path(UPLOAD_DIR) / username
    if not user_dir.exists():
        raise HTTPException(status_code=404, detail="User directory not found")

    file_names = [f.name for f in user_dir.glob("*") if f.is_file()]
    matches = process.extract(query, file_names, limit=limit)

    results = [
        {
            "file_name": match[0],
            "file_url": f"{BASE_URL}/uploads/{username}/{match[0]}",
            "score": match[1],
        }
        for match in matches
        if match[1] >= 60
    ]

    return JSONResponse(content={"results": results[:limit]})


@app.post("/verify")
async def verify_api_key_endpoint(authorization: str = Header(None)):
    try:
        username = await verify_api_key(authorization)
        return JSONResponse(
            content={
                "status": "success",
                "message": "API key is valid",
                "username": username,
            }
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code, content={
                "status": "error", "message": e.detail}
        )


@app.post("/generate-key")
async def generate_api_key(username: str):
    new_key = str(uuid4())

    keys_data = load_json(KEY_FILE)
    if username in keys_data:
        return JSONResponse(
            status_code=409,
            content={"status": "error", "message": "Username already exists"},
        )
    keys_data.append({"user": username, "key": new_key})

    save_json(KEY_FILE, keys_data)

    init_globals()

    return JSONResponse(content={"key": new_key})


@app.get("/{generated_filename}")
async def serve_file_embed(generated_filename: str, request: Request):
    original_file_path = file_name_map.get(generated_filename.split(".")[0])

    if not original_file_path or not os.path.exists(original_file_path):
        raise HTTPException(status_code=404, detail="File not found")

    username = Path(original_file_path).parent.name
    file_name = Path(original_file_path).name
    file_url = f"{BASE_URL}/uploads/{username}/{file_name}"

    file_mime, _ = mimetypes.guess_type(original_file_path)
    file_type = "other"

    if file_mime and file_mime.startswith("image"):
        file_type = "image"
    elif file_mime and file_mime.startswith("video"):
        file_type = "video"

    return templates.TemplateResponse(
        "embed.html",
        {
            "request": request,
            "file_name": file_name,
            "file_url": file_url,
            "file_type": file_type,
            "username": username,
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 8000))
    )
