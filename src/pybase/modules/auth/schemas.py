from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    real_name: str = Field(min_length=1, max_length=64)
    mobile: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=128)
    role: str | None = Field(default="user", max_length=64)


class UserLogin(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: str
    mobile: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    job_title: str | None = None
    role: str | None = None
    status: str
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserUpdate(BaseModel):
    real_name: str | None = Field(default=None, max_length=64)
    mobile: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=128)
    avatar_url: str | None = Field(default=None, max_length=500)
    job_title: str | None = Field(default=None, max_length=64)


class ChangePassword(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"