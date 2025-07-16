"""
# main.py
This file contains the main application logic for the cloud bucket service.
It includes endpoints for user authentication, bucket management, file operations, and sharing files.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from minio_client import client
from schemas import UserCreate, Token
from utilities import create_access_token, verify_password, hash_password, get_current_user
from database import get_db, engine
from models import Base, User, Bucket
from fastapi.responses import StreamingResponse
from schemas import ShareFileRequest
from models import Files, FilePermission, FileVersion, PermissionType
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
def upload(bucket: str, file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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

    # Add file entry to database
    bucket_obj = db.query(Bucket).filter(Bucket.name == bucket_name, Bucket.owner_id == user.id).first()
    if not bucket_obj:
        raise HTTPException(status_code=404, detail="Bucket not found in database")
    new_file = Files(name=file.filename, bucket_id=bucket_obj.id)
    db.add(new_file)
    db.commit()
    db.refresh(new_file)

    return {"filename": file.filename, "status": "Upload successful", "file_id": new_file.id}


@app.get("/files")
def list_files(bucket: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bucket_name = f"{user.username}-{bucket}"
    if not client.bucket_exists(bucket_name):
        raise HTTPException(status_code=404, detail="Bucket not found")
    objects = client.list_objects(bucket_name)
    result = []
    for obj in objects:
        file_record = db.query(Files).filter(
            Files.name == obj.object_name,
            Files.bucket.has(name=bucket_name)
        ).first()
        result.append({
            "filename": obj.object_name,
            "file_id": file_record.id if file_record else None
        })
    return result


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
    bucket_obj = db.query(Bucket).filter(Bucket.name == bucket_name, Bucket.owner_id == user.id).first()
    if bucket_obj:
        # Delete all files associated with the bucket
        db.query(Files).filter(Files.bucket_id == bucket_obj.id).delete()
        # Delete the bucket itself
        db.delete(bucket_obj)
        db.commit()
    return {"message": f"Bucket {bucket_name} deleted"}


@app.delete("/delete_files")
def delete_files(bucket:dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bucket_name = f"{user.username}-{bucket['bucket']}"
    if not client.bucket_exists(bucket_name):
        raise HTTPException(status_code=404, detail="Bucket not found")
    try:
        filenames = json.loads(bucket['filename'])
        bucket_obj = db.query(Bucket).filter(Bucket.name == bucket_name, Bucket.owner_id == user.id).first()
        for file in filenames:
            client.remove_object(bucket_name, str(file))
            print(f"File {file} deleted from bucket {bucket_name}")
            # Delete from database
            if bucket_obj:
                db.query(Files).filter(Files.name == str(file), Files.bucket_id == bucket_obj.id).delete()
        db.commit()
        return {"message": f"File {filenames} deleted from bucket {bucket_name}"}
    except Exception as e:
        print("Delete file error:", e)
        raise HTTPException(status_code=404, detail="File not found")


@app.post("/share")
def share_file(data: ShareFileRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Find the file by name and bucket
    bucket_name = f"{user.username}-{data.bucket}"
    file = db.query(Files).join(Bucket).filter(
        Files.name == data.filename,
        Bucket.name == bucket_name
    ).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    if file.bucket.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to share this file")

    # Check if file is already shared
    existing_permission = db.query(FilePermission).filter(FilePermission.file_id == file.id).first()
    if existing_permission:
        raise HTTPException(status_code=400, detail="File has already been shared")

    # Find the shared user by username
    shared_user = db.query(User).filter(User.username == data.shared_with_username).first()
    if not shared_user:
        raise HTTPException(status_code=404, detail="Shared user not found")

    # Add permission in database
    permission = FilePermission(
        file_id=file.id,
        shared_with_user_id=shared_user.id,
        permission_type="read"
    )
    db.add(permission)
    db.commit()

    # Share in MinIO by creating a bucket policy for the specific shared user
    object_name = file.name
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": [f"arn:aws:iam::minio:user/{shared_user.username}"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket_name}/{object_name}"]
            }
        ]
    }
    try:
        client.set_bucket_policy(bucket_name, json.dumps(policy))
    except Exception as e:
        print("MinIO policy error:", e)
        raise HTTPException(status_code=500, detail="Failed to set MinIO bucket policy")

    return {"message": "File shared successfully"}


@app.get("/shared_with_me")
def files_shared_with_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    permissions = db.query(FilePermission).filter(FilePermission.shared_with_user_id == user.id).all()
    shared_files = []
    for perm in permissions:
        file = db.query(Files).filter(Files.id == perm.file_id).first()
        if file:
            bucket = db.query(Bucket).filter(Bucket.id == file.bucket_id).first()
            shared_files.append({
                "filename": file.name,
                "bucket": bucket.name if bucket else None,
                "permission_type": perm.permission_type
            })
    return shared_files


@app.get("/download_shared")
def download_shared_file(bucket: str, filename: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check if user has permission to access the file
    bucket_obj = db.query(Bucket).filter(Bucket.name == bucket).first()
    file = db.query(Files).filter(Files.name == filename, Files.bucket_id == bucket_obj.id).first() if bucket_obj else None
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    permission = db.query(FilePermission).filter(
        FilePermission.file_id == file.id,
        FilePermission.shared_with_user_id == user.id
    ).first()
    if not permission:
        raise HTTPException(status_code=403, detail="You do not have access to this file")
    try:
        file_data = client.get_object(bucket, filename)
        return StreamingResponse(
            file_data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        print("Download shared file error:", e)
        raise HTTPException(status_code=404, detail="Download failed")
