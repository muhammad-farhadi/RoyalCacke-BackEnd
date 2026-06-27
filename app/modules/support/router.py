# app/modules/support/router.py
import os

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
import os
import time
import shutil
from fastapi import UploadFile, File
from app.core.database import get_db
from app.core.security import ALGORITHM, SECRET_KEY
from app.core.dependencies import get_current_user, RequirePermission
from app.modules.users.models import User
from jose import jwt, JWTError

from .models import SupportMessage
from . import schemas
from .manager import manager

router = APIRouter()
SUPPORT_MEDIA_DIR = "app/static/support/attachments"
os.makedirs(SUPPORT_MEDIA_DIR, exist_ok=True)


# ==========================================
# بخش اول: API های REST (برای لود کردن تاریخچه چت)
# ==========================================

@router.get("/history", response_model=List[schemas.MessageResponse])
def get_user_chat_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """کاربر عادی تاریخچه چت خودش را می‌بیند"""
    messages = db.query(SupportMessage).filter(
        SupportMessage.room_user_id == current_user.id
    ).order_by(SupportMessage.created_at.asc()).all()
    return messages


@router.get("/admin/history/{user_id}", response_model=List[schemas.MessageResponse])
def get_admin_chat_history(user_id: int, db: Session = Depends(get_db),
                           current_user=Depends(RequirePermission("support:read"))):
    """ادمین تاریخچه چت یک کاربر خاص را می‌بیند"""
    messages = db.query(SupportMessage).filter(
        SupportMessage.room_user_id == user_id
    ).order_by(SupportMessage.created_at.asc()).all()
    return messages


@router.get("/admin/conversations", response_model=List[schemas.ConversationResponse])
def get_all_conversations(db: Session = Depends(get_db), current_user=Depends(RequirePermission("support:read"))):
    """ادمین لیستی از کاربرانی که پیام داده‌اند را می‌بیند (صندوق ورودی)"""
    # در یک دیتابیس بزرگ این کوئری نیاز به بهینه‌سازی (Group By پیشرفته) دارد،
    # اما برای شروع این منطق لیست کاربرانی که پیام داده‌اند را برمی‌گرداند.
    subquery = db.query(SupportMessage.room_user_id).distinct().subquery()
    users = db.query(User).filter(User.id.in_(subquery)).all()

    conversations = []
    for u in users:
        last_msg = db.query(SupportMessage).filter(SupportMessage.room_user_id == u.id).order_by(
            desc(SupportMessage.created_at)).first()
        unread = db.query(SupportMessage).filter(SupportMessage.room_user_id == u.id, SupportMessage.is_read == False,
                                                 SupportMessage.sender_id != current_user.id).count()

        conversations.append(
            schemas.ConversationResponse(
                user_id=u.id,
                user_full_name=u.full_name,
                last_message=last_msg.content if last_msg else "",
                unread_count=unread,
                last_activity=last_msg.created_at if last_msg else u.created_at
            )
        )
    return sorted(conversations, key=lambda x: x.last_activity, reverse=True)


@router.post("/upload_media", status_code=status.HTTP_201_CREATED)
def upload_chat_media(
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    این API فایل را می‌گیرد و لینک آن را برمی‌گرداند تا در سوکت ارسال شود.
    """
    ext = file.filename.split(".")[-1].lower()

    # تشخیص نوع فایل برای کلاینت
    if ext in ["jpg", "jpeg", "png", "webp"]:
        attachment_type = "image"
    elif ext in ["mp3", "wav", "ogg", "m4a"]:
        attachment_type = "voice"
    elif ext in ["mp4", "mkv", "avi"]:
        attachment_type = "video"
    else:
        attachment_type = "document"

    filename = f"chat_{current_user.id}_{int(time.time())}.{ext}"
    file_path = os.path.join(SUPPORT_MEDIA_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "attachment_url": f"/static/support/attachments/{filename}",
        "attachment_type": attachment_type
    }


# ==========================================
# بخش دوم: WebSocket (برای چت آنلاین)
# ==========================================

async def get_user_from_token(token: str, db: Session) -> User:
    """تابع کمکی برای تایید هویت در وب‌سوکت"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_sub = payload.get("sub")
        if user_sub is None:
            raise ValueError("Token invalid")
        user = db.query(User).filter(User.phone_number == str(user_sub)).first()
        if not user:
            raise ValueError("User not found")
        return user
    except (JWTError, ValueError):
        return None


@router.websocket("/ws")
async def websocket_chat(
        websocket: WebSocket,
        token: str = Query(...),
        target_user_id: int = Query(None),
        db: Session = Depends(get_db)
):
    user = await get_user_from_token(token, db)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    is_admin = getattr(user, 'is_superuser', False)
    room_id = target_user_id if (is_admin and target_user_id) else user.id

    await manager.connect(websocket, room_id)

    try:
        while True:
            # ---> تغییر مهم: حالا به جای text ساده، JSON دریافت می‌کنیم <---
            data = await websocket.receive_json()

            content = data.get("content", "")
            attachment_url = data.get("attachment_url", None)
            attachment_type = data.get("attachment_type", None)

            # ذخیره در دیتابیس با پشتیبانی از مدیا
            new_message = SupportMessage(
                room_user_id=room_id,
                sender_id=user.id,
                content=content,
                attachment_url=attachment_url,
                attachment_type=attachment_type
            )
            db.add(new_message)
            db.commit()
            db.refresh(new_message)

            # ساخت پکیج پاسخ برای ارسال به کلاینت (فرانت‌اند)
            response_data = {
                "id": new_message.id,
                "sender_id": user.id,
                "sender_name": user.full_name,
                "content": content,
                "attachment_url": attachment_url,
                "attachment_type": attachment_type,
                "created_at": new_message.created_at.isoformat()
            }

            await manager.send_personal_message(response_data, room_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
