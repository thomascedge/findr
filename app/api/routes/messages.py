from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.schemas.schemas import MessageSend, MessageOut, MessageEdit
from app.models.models import User, Chat, ChatMember, Message, utcnow
from app.core.security import get_current_user

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/send", response_model=MessageOut, status_code=201)
async def send_message(
    payload: MessageSend,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    recipient_id: UUID = None,
    chat_id: UUID = None,
):
    if not recipient_id and not chat_id:
        raise HTTPException(status_code=400, detail="Provide either recipient_id or chat_id.")
    if recipient_id and chat_id:
        raise HTTPException(status_code=400, detail="Provide either recipient_id or chat_id, not both.")
    
    if recipient_id:
        result = await db.execute(select(User).where(User.id == recipient_id))
        recipient = result.scalar_one_or_none()
        if not recipient:
            raise HTTPException(status_code=404, detail="User does not exist.")
        if not recipient.is_active:
            raise HTTPException(status_code=404, detail="User not found.")

        existing_chat_result = await db.execute(
            select(ChatMember.chat_id)
            .where(ChatMember.user_id == current_user.id)
            .where(ChatMember.chat_id.in_(
                select(ChatMember.chat_id).where(ChatMember.user_id == recipient_id)
            ))
        )
        existing_chat_id = existing_chat_result.scalar_one_or_none()

        if existing_chat_id:
            chat_id = existing_chat_id
        else:
            new_chat = Chat(is_group=False)
            db.add(new_chat)
            await db.flush()

            db.add(ChatMember(chat_id=new_chat.id, user_id=current_user.id, is_admin=False))
            db.add(ChatMember(chat_id=new_chat.id, user_id=recipient_id, is_admin=False))
            await db.flush()
            chat_id = new_chat.id

    if chat_id:
        result = await db.execute(select(Chat).where(Chat.id == chat_id))
        chat = result.scalar_one_or_none()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat does not exist.")

        member_result = await db.execute(
            select(ChatMember).where(
                ChatMember.chat_id == chat_id,
                ChatMember.user_id == current_user.id,
            )
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="You are not a member of this chat.")

    new_message = Message(
        chat_id=chat_id,
        sender_id=current_user.id,
        body=payload.body,
    )
    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)
    return new_message
    

@router.get("/thread", response_model=list[MessageOut])
async def get_thread(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    recipient_id: UUID = None,
    chat_id: UUID = None,
    limit: int = 50,
):
    if not recipient_id and not chat_id:
        raise HTTPException(status_code=400, detail="Provide either recipient_id or chat_id.")
    if recipient_id and chat_id:
        raise HTTPException(status_code=400, detail="Provide either recipient_id or chat_id, not both.")

    if recipient_id:
        # Find the DM chat between current_user and recipient
        existing_chat_result = await db.execute(
            select(ChatMember.chat_id)
            .where(ChatMember.user_id == current_user.id)
            .where(ChatMember.chat_id.in_(
                select(ChatMember.chat_id).where(ChatMember.user_id == recipient_id)
            ))
        )
        chat_id = existing_chat_result.scalar_one_or_none()
        if not chat_id:
            raise HTTPException(status_code=404, detail="No conversation found with this user.")

    if chat_id:
        # Verify chat exists
        chat_result = await db.execute(select(Chat).where(Chat.id == chat_id))
        if not chat_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Chat does not exist.")

        # Verify current_user is a member
        member_result = await db.execute(
            select(ChatMember).where(
                ChatMember.chat_id == chat_id,
                ChatMember.user_id == current_user.id,
            )
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="You are not a member of this chat.")

    # Query messages ordered by most recent first, apply limit
    messages_result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .where(Message.deleted_at == None)
        .order_by(Message.sent_at.desc())
        .limit(limit)
    )
    return messages_result.scalars().all()

@router.patch("/{message_id}")
async def edit_message(message_id: UUID, payload: MessageEdit, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if message.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own messages" )
    
    message.body = payload.body
    message.edited_at = utcnow()
    await db.commit()
    return {"status": "edited"}

@router.delete("/{message_id}")
async def delete_message(message_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if message.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own messages" )
    
    message.deleted_at = utcnow()
    await db.commit()
    return {"status": "deleted"}