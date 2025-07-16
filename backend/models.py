from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from database import Base
import enum
import datetime

class AccessType(str, enum.Enum):
    public = "public"
    private = "private"

class PermissionType(str, enum.Enum):
    read = "read"
    write = "write"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    buckets = relationship("Bucket", back_populates="owner")
    shared_files = relationship("FilePermission", back_populates="shared_with")

class Bucket(Base):
    __tablename__ = "buckets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="buckets")
    files = relationship("Files", back_populates="bucket")

class Files(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    bucket_id = Column(Integer, ForeignKey("buckets.id"))
    size = Column(Integer)
    access_type = Column(Enum(AccessType))
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    locked_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    bucket = relationship("Bucket", back_populates="files")
    permissions = relationship("FilePermission", back_populates="file")
    versions = relationship("FileVersion", back_populates="file")

class FilePermission(Base):
    __tablename__ = "file_permissions"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"))
    shared_with_user_id = Column(Integer, ForeignKey("users.id"))
    permission_type = Column(Enum(PermissionType))

    file = relationship("Files", back_populates="permissions")
    shared_with = relationship("User", back_populates="shared_files")

class FileVersion(Base):
    __tablename__ = "file_versions"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    content_hash = Column(String)

    file = relationship("Files", back_populates="versions")
