from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

class SetPassword(BaseModel):
    password: str    

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True