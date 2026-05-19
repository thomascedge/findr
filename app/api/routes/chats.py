from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.schemas import ChatOut
from app.models.models import User, Chat, ChatMember
from app.core.security import get_current_user

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("/", response_model=ChatOut, status_code=201)
async def create_group_chat(
    member_ids: list[UUID],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if len(member_ids) < 2:
        raise HTTPException(status_code=400, detail="Group chat cannot be created with less than 2 users.")
    
    for user_id in member_ids:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
    new_chat = Chat(is_group=True)
    db.add(new_chat)
    await db.flush()

    db.add(ChatMember(chat_id=new_chat.id, user_id=current_user.id, is_admin=True))
    for member_id in member_ids:
        db.add(ChatMember(chat_id=new_chat.id, user_id=member_id, is_admin=False))
    
    await db.commit()
    return new_chat


@router.get("/{chat_id}/members", response_model=list[UUID])
async def get_chat_members(
    chat_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Chat).where(Chat.id == chat_id))
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat does not exist.")
    
    result = await db.execute(
        select(ChatMember)
        .join(User, User.id == ChatMember.user_id)
        .where(
            ChatMember.chat_id == chat_id,
            User.is_active == True
        )
    )
    chat_member = result.scalars().all()

    member_ids = []
    for member in chat_member:
        member_ids.append(member.user_id)

    if current_user.id not in member_ids:
        raise HTTPException(status_code=403, detail="User not member of chat.")

    return member_ids


@router.post("/{chat_id}/members")
async def add_member(
    chat_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Chat).where(Chat.id == chat_id))
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat does not exist.")

    result = await db.execute(select(User).where(User.id == user_id))
    user_to_add = result.scalar_one_or_none()
    if not user_to_add or not user_to_add.is_active:
        raise HTTPException(status_code=404, detail="User not found.")

    result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.user_id == current_user.id)
    )
    user_controlling = result.scalar_one_or_none()
    if not user_controlling:
        raise HTTPException(status_code=403, detail="You are not a member of this chat.")

    result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.user_id == user_id)
    )
    user_member = result.scalar_one_or_none()
    if user_member:
        raise HTTPException(status_code=400, detail="User is already a member of this chat.")

    db.add(ChatMember(chat_id=chat_id, user_id=user_id, is_admin=False))
    await db.commit()
    return {"status": "added"}


@router.delete("/{chat_id}/members/{user_id}")
async def remove_member(
    chat_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Chat).where(Chat.id == chat_id))
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat does not exist.")

    result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You are not a member of this chat.")

    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found.")

    result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.user_id == user_id)
    )
    chat_member = result.scalar_one_or_none()
    if not chat_member:
        raise HTTPException(status_code=404, detail="User is not a member of this chat.")

    if chat_member.is_admin:
        raise HTTPException(status_code=400, detail="Cannot remove an admin.")

    await db.execute(delete(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.user_id == user_id))
    await db.commit()
    return {"status": "removed"}

@router.patch("/{chat_id}/members/admin/{user_id}")
async def transfer_admin_access(
    chat_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Chat).where(Chat.id == chat_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Chat does not exist.")

    # Verify current_user is an admin
    result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.user_id == current_user.id)
    )
    current_member = result.scalar_one_or_none()
    if not current_member or not current_member.is_admin:
        raise HTTPException(status_code=403, detail="You must be an admin to perform this action.")

    # Verify target user is a member
    result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id, ChatMember.user_id == user_id)
    )
    target_member = result.scalar_one_or_none()
    if not target_member:
        raise HTTPException(status_code=404, detail="User is not a member of this chat.")

    if target_member.is_admin:
        raise HTTPException(status_code=400, detail="User is already an admin.")

    target_member.is_admin = True
    current_member.is_admin = False
    await db.commit()
    return {"status": "updated"}