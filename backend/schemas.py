from pydantic import BaseModel

class ShareFileRequest(BaseModel):
    filename: str
    bucket: str
    shared_with_username: str

class UserCreate(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
