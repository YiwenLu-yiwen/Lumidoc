"""Account administration within the auth module; no project-content access."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
import asyncpg
import logging

logger = logging.getLogger(__name__)

class AccountUpdate(BaseModel):
    email: EmailStr
    nickname: str = Field(max_length=80)
    current_password: str = Field(min_length=1, max_length=256)

class AdminUserUpdate(BaseModel):
    is_active: bool
    is_superuser: bool


def account_router(service, current_user):
    router = APIRouter(prefix='/api')

    async def administrator(user=Depends(current_user)):
        if not user.is_active or not user.is_superuser:
            raise HTTPException(403, 'Administrator access required')
        return user

    async def pool():
        if service.db_pool is None:
            await service._init_db_pool()
        return service.db_pool

    @router.patch('/users/me/', response_model=None)
    async def update_account(body: AccountUpdate, user=Depends(current_user)):
        if not await service.authenticate_user(user.username, body.current_password):
            raise HTTPException(403, 'Current password is incorrect')
        try:
            async with (await pool()).acquire() as conn:
                await conn.execute('UPDATE users SET email=$1, nickname=$2, updated_at=NOW() WHERE id=$3', str(body.email), body.nickname, user.id)
        except asyncpg.UniqueViolationError:
            raise HTTPException(409, 'Email is already in use')
        return await service.get_user(user.id)

    @router.get('/admin/users')
    async def users(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), admin=Depends(administrator)):
        async with (await pool()).acquire() as conn:
            rows = await conn.fetch('SELECT id, username, email, nickname, is_active, is_superuser, created_at FROM users ORDER BY id LIMIT $1 OFFSET $2', limit, offset)
            total = await conn.fetchval('SELECT COUNT(*) FROM users')
        return {'users': [dict(row) for row in rows], 'total': total}

    @router.patch('/admin/users/{user_id}')
    async def update_user(user_id: int, body: AdminUserUpdate, admin=Depends(administrator)):
        if user_id == admin.id:
            raise HTTPException(409, 'You cannot change your own administrator status')
        async with (await pool()).acquire() as conn:
            # Serialize changes so concurrent requests cannot disable every admin.
            async with conn.transaction():
                await conn.execute('LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE')
                actor = await conn.fetchrow('SELECT is_active, is_superuser FROM users WHERE id=$1', admin.id)
                if not actor or not actor['is_active'] or not actor['is_superuser']:
                    raise HTTPException(403, 'Administrator access revoked')
                existing = await conn.fetchrow('SELECT id FROM users WHERE id=$1', user_id)
                if not existing:
                    raise HTTPException(404, 'User not found')
                await conn.execute('UPDATE users SET is_active=$1, is_superuser=$2, updated_at=NOW() WHERE id=$3', body.is_active, body.is_superuser, user_id)
        logger.info('admin_user_update actor=%s target=%s active=%s superuser=%s', admin.id, user_id, body.is_active, body.is_superuser)
        return {'success': True}

    return router
