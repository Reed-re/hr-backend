from fastapi import APIRouter,Depends,BackgroundTasks
from core.cache import HRCache,InviteInfoSchema
from models.user import UserModel
from schemas.user_schema import UserLoginSchema,UserLoginRespSchema,UserInviteSchema
from dependencies import get_session_instance,AuthHandler,get_auth_handler,get_cache_instance,get_super_user
from models import AsyncSession
from repository.user_repo import UserRepo,DepartmentRepo
from fastapi.exceptions import HTTPException
from fastapi import status
import string,random
from tasks import send_invite_email_task
from schemas import ResponseSchema
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

@router.post("/invite", summary="邀请用户", response_model=ResponseSchema)
async def invite_user(
    invite_data: UserInviteSchema,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session_instance),
    cache: HRCache = Depends(get_cache_instance),
    _: UserModel = Depends(get_super_user),
):
    async with session.begin():
        user_repo = UserRepo(session)
        user = await user_repo.get_by_email(str(invite_data.email))
        if user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该邮箱已存在！")
        department_repo = DepartmentRepo(session)
        department =await department_repo.get_by_id(department_id=invite_data.department_id)
        if not department:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该部门不存在！")
    # 生成6位数字验证码
    invite_code = "".join(random.sample(string.digits, 6))
    # 存储到redis缓存中
    invite_info = InviteInfoSchema(
        email=invite_data.email,
        department_id=invite_data.department_id,
        invite_code=invite_code,
    )
    await cache.set_invite_info(invite_info)
    # 发送邮件
    background_tasks.add_task(send_invite_email_task, str(invite_info.email), invite_code)
    return ResponseSchema()