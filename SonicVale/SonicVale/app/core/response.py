# app/core/response.py
# Pydantic v2 已废弃 pydantic.generics.GenericModel,改用 BaseModel + Generic[T]
from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar("T")

class Res(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: Optional[T] = None
