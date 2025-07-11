from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from minio_client import client
from schemas import UserCreate, Token
from utilities import create_access_token, verify_password, hash_password, get_current_user
from database import get_db, engine
from models import Base, User, Bucket
from fastapi.responses import StreamingResponse
import io
import json

Base.metadata.create_all(bind=engine)
app = FastAPI()


@app.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="User already exists")
    new_user = User(username=user.username, hashed_password=hash_password(user.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created"}

@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid login")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/buckets")
def create_bucket(bucket: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bucket_name = f"{user.username}-{bucket['bucket']}"
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
    new_bucket = Bucket(name=bucket_name, owner_id=user.id)
    db.add(new_bucket)
    db.commit()
    return {"message": f"Bucket {bucket_name} created"}

@app.post("/upload")
def upload(bucket: str, file: UploadFile = File(...), user: User = Depends(get_current_user)):
    bucket_name = f"{user.username}-{bucket}"
    if not client.bucket_exists(bucket_name):
        raise HTTPException(status_code=404, detail="Bucket not found")

    content = file.file.read()
    stream = io.BytesIO(content)

    client.put_object(
        bucket_name=bucket_name,
        object_name=file.filename,
        data=stream,
        length=len(content),
        content_type=file.content_type
    )

    return {"filename": file.filename, "status": "Upload successful"}


@app.get("/files")
def list_files(bucket: str, user: User = Depends(get_current_user)):
    bucket_name = f"{user.username}-{bucket}"
    if not client.bucket_exists(bucket_name):
        raise HTTPException(status_code=404, detail="Bucket not found")
    objects = client.list_objects(bucket_name)
    return [obj.object_name for obj in objects]


@app.get("/download")
def download_file(bucket: str, filename: str, user: User = Depends(get_current_user)):
    bucket_name = f"{user.username}-{bucket}"

    try:
        file_data = client.get_object(bucket_name, filename)
        return StreamingResponse(
            file_data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        print("Download error:", e)
        raise HTTPException(status_code=404, detail="Download failed")


@app.delete("/delete_bucket")
def delete_bucket(bucket: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bucket_name = f"{user.username}-{bucket}"
    if not client.bucket_exists(bucket_name):
        raise HTTPException(status_code=404, detail="Bucket not found")
    client.remove_bucket(bucket_name)
    db.query(Bucket).filter(Bucket.name == bucket_name).delete()
    db.commit()
    return {"message": f"Bucket {bucket_name} deleted"}


@app.delete("/delete_files")
def delete_files(bucket:dict, user: User = Depends(get_current_user)):
    bucket_name = f"{user.username}-{bucket['bucket']}"
    if not client.bucket_exists(bucket_name):
        raise HTTPException(status_code=404, detail="Bucket not found")
    try:
        filenames = json.loads(bucket['filename'])
        for file in filenames:
            client.remove_object(bucket_name, str(file))
            print(f"File {file} deleted from bucket {bucket_name}")
        return {"message": f"File {filenames} deleted from bucket {bucket_name}"}
    except Exception as e:
        print("Delete file error:", e)
        raise HTTPException(status_code=404, detail="File not found")
