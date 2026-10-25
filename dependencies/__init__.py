from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import HRCache
from models.user import UserModel,UserStatus
from repository.user_repo import UserRepo
from core.auth import AuthHandler
from models import AsyncSessionFactory
from fastapi import Depends, HTTPException, status

auth_handler = AuthHandler()

async def get_session_instance():
    session:AsyncSession = AsyncSessionFactory()
    try:
        yield session
    finally:
        await session.close()

async def get_auth_handler() -> AuthHandler:
    return auth_handler

async def get_user_id(
    iss: str = Depends(auth_handler.auth_access_dependency),
):
    return iss

async def get_current_user(
    iss: str = Depends(get_user_id),
    session: AsyncSession = Depends(get_session_instance),
) -> UserModel:
    async with session.begin():
        user_repo = UserRepo(session)
        user = await user_repo.get_by_id(iss)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在！")
        if user.status != UserStatus.ACTIVE:
            raise HTTPException(status.HTTP_403_FORBIDDEN,detail="该员工状态不可用，请联系管理员！")
        return user

async def get_super_user(
    current_user: UserModel = Depends(get_current_user),
):
    if current_user.is_superuser:
        return current_user
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，仅superuser可操作！")

def get_cache_instance():
    return HRCache()