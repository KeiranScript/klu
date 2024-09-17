from fastapi import FastAPI, Depends, File, UploadFile, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from collections import Counter
from datetime import datetime
from rapidfuzz import process
from threading import Lock
from pathlib import Path
from uuid import uuid4

import string
import random
import json
import os

from modules.middleware import (
    verify_api_key, validate_file, handle_file_upload,
    rate_limit
)

app = FastAPI()

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static/zoe", StaticFiles(directory="static/zoe"), name="zoe")

KEY_FILE = "json/keys.json"
DEL_FILE = "json/delete.json"
UPLOAD_DIR = "uploads"
BASE_URL = "https://kuuichi.xyz"
ZOE_VIEWS_FILE = "json/zoe_views.json"

templates = Jinja2Templates(directory="templates")
file_delete_map = {}
file_name_map = {}
keys = {}
file_locks = {}

def load_json(file_path: str):
    return json.load(open(file_path)) if os.path.exists(file_path) else {}

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

def format_file_size(size_in_bytes: int) -> str:
    return f"{size_in_bytes / 1024**2:.2f} MB" if size_in_bytes >= 1024**2 else f"{size_in_bytes / 1024:.2f} KB"

def load_zoe_views() -> int:
    if os.path.exists(ZOE_VIEWS_FILE):
        with open(ZOE_VIEWS_FILE, 'r') as file:
            return json.load(file).get("zoe_views", 0)
    return 0

def save_zoe_views(views: int):
    with open(ZOE_VIEWS_FILE, 'w') as file:
        json.dump({"zoe_views": views}, file, indent=4)

def format_size(size_in_bytes: int) -> str:
    if size_in_bytes >= 1024**3:
        return f"{size_in_bytes / 1024**3:.2f} GB"
    if size_in_bytes >= 1024**2:
        return f"{size_in_bytes / 1024**2:.2f} MB"
    if size_in_bytes >= 1024:
        return f"{size_in_bytes / 1024:.2f} KB"
    return f"{size_in_bytes} B"

def generate_random_filename(length=8) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

zoe_views = load_zoe_views()
init_globals()

@app.get("/ohhq")
async def ohhq():
    return RedirectResponse(url='https://ohhq.gay', status_code=301)

@app.post("/")
async def upload(file: UploadFile = File(...), username: str = Depends(verify_api_key)):
    # request: Request = Request(scope={"type": "http"})
    # if request.method != "POST":
    #     return RedirectResponse(url='https://e-z.bio/kc', status_code=301)
    
    with acquire_lock(file.filename):
        rate_limit(username)
        validate_file(file)
        file_path, file_size, file_type, upload_time = handle_file_upload(file, username, UPLOAD_DIR)
        generated_name = generate_random_filename()
        file_name_map[f"{generated_name}{file_path.suffix}"] = file_path
        delete_uuid = str(uuid4())
        file_delete_map[delete_uuid] = str(file_path.resolve())
        save_json(DEL_FILE, file_delete_map)

        return JSONResponse(content={
            "file_url": f"{BASE_URL}/files/{generated_name}{file_path.suffix}",
            "file-size": format_file_size(file_size),
            "file-type": file_type,
            "date-uploaded": upload_time,
            "delete_url": f"{BASE_URL}/delete/{delete_uuid}"
        })

@app.get("/uploads/{username}/{file_name}")
async def serve_embed(request: Request, username: str, file_name: str):
    file_path = Path(UPLOAD_DIR) / username / file_name
    if not file_path.exists():
        return JSONResponse(content={"error": "File not found"}, status_code=404)

    file_url = f"{BASE_URL}/uploads/{username}/{file_name}"

    return templates.TemplateResponse("embed.html", {
        "request": request,
        "file_name": file_name,
        "file_url": file_url,
        "username": username
    })

@app.get("/delete/{delete_uuid}")
async def delete_file(request: Request, delete_uuid: str):
    file_path = file_delete_map.pop(delete_uuid, None)
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

    files = [{
        "file_name": file.name,
        "file_url": f"{BASE_URL}/uploads/{username}/{file.name}",
        "file-size": format_file_size(file.stat().st_size),
        "file-type": file.suffix[1:] if file.suffix else "unknown",
        "date-uploaded": datetime.fromtimestamp(file.stat().st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
        "delete_url": f"{BASE_URL}/delete/{next((key for key, value in file_delete_map.items() if value == str(file.resolve())), 'N/A')}"
    } for file in user_dir.glob("*") if file.is_file()]

    return JSONResponse(content={"files": files})

@app.get("/{generated_filename}")
async def serve_file(generated_filename: str):
    original_file_path = file_name_map.get(generated_filename)

    if not original_file_path or not os.path.exists(original_file_path):
        return JSONResponse(content={"error": "File not found"}, status_code=404)
    
    return RedirectResponse(url=f"{BASE_URL}/uploads/{original_file_path.parent.name}/{original_file_path.name}")

@app.get("/search")
async def search_files(query: str, username: str = Depends(verify_api_key)):
    user_dir = Path(UPLOAD_DIR) / username
    if not user_dir.exists():
        return JSONResponse(content={"error": "User directory not found"}, status_code=404)

    file_names = [f.name for f in user_dir.glob("*") if f.is_file()]
    matches = process.extract(query, file_names, limit=10)

    results = [{
        "file_name": match[0],
        "file_url": f"{BASE_URL}/uploads/{username}/{match[0]}",
        "score": match[1]
    } for match in matches]

    return JSONResponse(content={"results": results})



@app.get("/zoe")
async def serve_random_zoe_file():
    global zoe_views
    zoe_dir = Path("static/zoe")

    if not zoe_dir.exists() or not any(zoe_dir.iterdir()):
        return JSONResponse(content={"error": "No files found in the /static/zoe directory"}, status_code=404)

    random_file = random.choice([f for f in zoe_dir.iterdir() if f.is_file()])
    zoe_views += 1
    save_zoe_views(zoe_views)

    return RedirectResponse(url=f"/static/zoe/{random_file.name}", status_code=302)

@app.get("/info")
async def get_server_info():
    upload_dir = Path(UPLOAD_DIR)
    total_storage_used = sum(f.stat().st_size for f in upload_dir.glob('**/*') if f.is_file())
    total_uploads = sum(1 for _ in upload_dir.glob('**/*') if _.is_file())
    total_users = sum(1 for _ in upload_dir.iterdir() if _.is_dir())

    return JSONResponse(content={
        "storage_used": format_size(total_storage_used),
        "uploads": total_uploads,
        "users": total_users,
        "zoe_views": zoe_views
    })

@app.get("/lb")
async def get_analytics():
    upload_files = [f for f in Path(UPLOAD_DIR).glob('**/*') if f.is_file()]
    user_uploads = Counter(f.parent.name for f in upload_files)

    zoe_files = [f for f in Path("static/zoe").glob('**/*') if f.is_file()]
    zoe_views = sum(1 for _ in zoe_files)

    return JSONResponse(content={
        "user_uploads": dict(user_uploads),
        "zoe_views": zoe_views
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)