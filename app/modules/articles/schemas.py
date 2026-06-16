# app/modules/articles/schemas.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


class ArticleBase(BaseModel):
    title: str = Field(..., max_length=200)
    slug: str = Field(..., description="آدرس یکتای مقاله برای SEO")
    content: str
    meta_description: Optional[str] = Field(None, max_length=160, description="حداکثر ۱۶۰ کاراکتر برای سئو")
    tags: Optional[str] = Field(None, description="کلمات کلیدی با ویرگول جدا شوند")


class ArticleCreate(ArticleBase):
    pass


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    content: Optional[str] = None
    meta_description: Optional[str] = None
    tags: Optional[str] = None


class ArticleResponse(ArticleBase):
    id: int
    author_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
