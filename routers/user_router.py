from fastapi import APIRouter,Depends
from models.user import UserModel
from schemas.user_schema import UserLoginSchema,UserLoginRespSchema
from dependencies import get_session_instance,AuthHandler,get_auth_handler
from models import AsyncSession
from repository.user_repo import UserRepo
from fastapi.exceptions import HTTPException
from fastapi import status
router =   APIRouter(prefix="/user", tags=["user"])

@router.post("/login",summary="登录",response_model=UserLoginRespSchema)
async def login(
    login_data:UserLoginSchema,
    session: AsyncSession = Depends(get_session_instance),
    auth_handler: AuthHandler = Depends(get_auth_handler)
):
    async with session.begin():
        user_repo = UserRepo(session)
        user: UserModel = await user_repo.get_by_email(str(login_data.email))
        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户不存在")
        if not user.check_password(str(login_data.password)):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="邮箱或密码错误！")
        tokens = auth_handler.encode_login_token(user.id)
        return {
            "access_token": tokens['access_token'],
            "refresh_token": tokens['refresh_token'],
            "user":user
        }

