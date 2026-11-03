from fastapi import APIRouter, Depends, HTTPException, UploadFile, File,status,BackgroundTasks
from dependencies import get_session_instance, get_current_user
from models import AsyncSession
from models.user import UserModel
import os
from settings import settings
router = APIRouter(prefix="/candidate", tags=["candidate"])
from uuid import uuid4
import aiofiles
from core.pdf import WordToPdfConverter
from loguru import logger
from repository.candidate_repo import ResumeRepo,CandidateRepo
from schemas.candidate_schema import ResumeUploadRespSchema,CandidateCreateSchema
from core.ocr import PaddleOcr
from schemas.candidate_schema import ResumeParseTaskRespSchema,ResumePaseSchema,ResumeParseTaskInfoRespSchema
from tasks import ocr_parse_resume_task
from dependencies import get_cache_instance
from core.cache import HRCache
from schemas import ResponseSchema
from repository.position_repo import PositionRepo
from repository.user_repo import UserRepo
from tasks import run_candidate_agent
from schemas.candidate_schema import CandidateSchema
from schemas.position_schema import PositionSchema
from schemas.user_schema import UserSchema
# 上传简历
@router.post(path="/resume/upload", summary="上传简历",response_model=ResumeUploadRespSchema)
async def resume_upload(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session_instance),
    current_user: UserModel = Depends(get_current_user),
):
    # 简历：图片、pdf、word
    allowed_mime_types = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "image/jpeg",
        "image/png",
        "image/jpg",
    ]
    if file.content_type not in allowed_mime_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该文件不支持！")

    # 2. 保存文件
    resume_dir = settings.RESUME_DIR
    file_extension = os.path.splitext(file.filename)[-1]
    unique_filename = f"{uuid4()}{file_extension}"
    file_path = os.path.join(resume_dir, unique_filename)
    # with open(file_path, "wb") as f:
    try:
        async with aiofiles.open(file_path, mode="wb") as fp:
            content = await file.read(1024)
            while content:
                await fp.write(content)
                content = await file.read(1024)
    finally:
        await fp.close()

    if file_extension == ".doc" or file_extension == ".docx":
        pdf_path = file_path.replace(file_extension, ".pdf")
        converter = WordToPdfConverter(
            word_path=file_path,
            output_pdf_path=pdf_path,
        )
        try:
            await converter.convert()
            file_path = pdf_path
        except Exception as e:
            logger.error(f"Word转PDF失败：{e}")

    async with session.begin():
        resume_repo = ResumeRepo(session=session)
        resume = await resume_repo.create_resume(file_path=file_path, uploader_id=current_user.id)
    return {"resume": resume}

@router.get("/resume/ocr/test")
async def resume_ocr_test():
    file_path = os.path.join(settings.RESUME_DIR, "e4765b9f-ec41-45d9-9674-eaa99992ef53.pdf")
    paddle_ocr = PaddleOcr()
    job_id = await paddle_ocr.create_job(file_path)
    jsonl_url = await paddle_ocr.poll_for_state(job_id)
    contents = await paddle_ocr.fetch_parsed_contents(jsonl_url)
    logger.info(contents)
    return "success"

@router.post(path="/resume/parse", summary="简历解析",response_model=ResumeParseTaskRespSchema)
async def parse_resume(
    resume_data: ResumePaseSchema,
    background_tasks: BackgroundTasks,
    _: UserModel = Depends(get_current_user),
):
    # 创建一个识别简历的后台任务
    task_id = str(uuid4())
    background_tasks.add_task(ocr_parse_resume_task, resume_id=resume_data.resume_id, task_id=task_id)
    return {"task_id": task_id}

@router.get(path="/resume/parse/{task_id}", summary="获取任务状态",response_model=ResumeParseTaskInfoRespSchema)
async def get_task_status(
    task_id: str,
    cache: HRCache = Depends(get_cache_instance),
    _: UserModel = Depends(get_current_user)
):
    task_info = await cache.get_task_info(task_id)
    return task_info.model_dump()

@router.post(path="/create", summary="创建候选人", response_model=ResponseSchema)
async def create_candidate(
    candidate_data: CandidateCreateSchema,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session_instance),
    current_user: UserModel = Depends(get_current_user),
):
    async with session.begin():
        candidate_dict = candidate_data.model_dump()
        candidate_dict['creator_id'] = current_user.id
        candidate_repo = CandidateRepo(session=session)
        candidate = await candidate_repo.create_candidate(candidate_dict)
        candidate_schema = CandidateSchema.model_validate(candidate)
        position_schema = PositionSchema.model_validate(candidate.position)
        interviewer_schema = UserSchema.model_validate(candidate.position.creator)

        background_tasks.add_task(
            run_candidate_agent,
            candidate=candidate_schema,
            position=position_schema,
            interviewer=interviewer_schema,
        )

    return ResponseSchema()

@router.get("/agent/test")
async def agent_test(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session_instance),
):
    async with session.begin():
        candidate_repo = CandidateRepo(session=session)
        position_repo = PositionRepo(session=session)
        user_repo = UserRepo(session=session)

        candidate_model = await candidate_repo.get_by_id("WVLFtDNUWF2jbr3Z2XYxAP")
        position_model = await position_repo.get_by_id("ja2RUwskDKNSBs4yf9E8d8")
        interviewer_model = await user_repo.get_by_id("cpoDFejuUgz4zykuFCU2gm")

        background_tasks.add_task(
            run_candidate_agent,
            candidate=CandidateSchema.model_validate(candidate_model),
            position=PositionSchema.model_validate(position_model),
            interviewer=UserSchema.model_validate(interviewer_model),
        )

    return {"result": "success"}