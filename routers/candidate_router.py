from fastapi import APIRouter, Depends, HTTPException, UploadFile, File,status
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
from repository.candidate_repo import ResumeRepo
from schemas.candidate_schema import ResumeUploadRespSchema
from core.ocr import PaddleOcr

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