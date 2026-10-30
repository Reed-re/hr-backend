from fastapi_mail import FastMail, MessageSchema
from aiosmtplib import SMTPResponseException
from loguru import logger
from core.mail import create_mail_instance
from settings import settings
import os
from models import AsyncSessionFactory
from core.cache import HRCache,TaskInfoSchema
from dependencies import get_cache_instance
from core.ocr import PaddleOcr
from repository.candidate_repo import ResumeRepo
from agents.resume import extract_candidate_info
from schemas.agent_schema import AgentCandidateSchema
async def send_email_task(message: MessageSchema):
    # 发送邮件
    mail: FastMail = create_mail_instance()
    try:
        await mail.send_message(message)
    except SMTPResponseException as e:
        if e.code == -1 and b'\\x00\\x00\\x00' in str(e).encode():
            logger.info("⚠️ 忽略 QQ 邮箱 SMTP 关闭阶段的非标准响应（邮件已成功发送）", enqueue=True)
        else:
            logger.error(f"邮件发送失败！{e}")

async def send_invite_email_task(
    email: str,
    invite_code: str
):
    # 发送邮件
    message = MessageSchema(
        subject="【Reed大王】注册邀请",
        recipients=[email],
        body=f"您好，您的邮箱是：{email}，验证码是：{invite_code}，一天内有效。",
        subtype="plain"
    )
    await send_email_task(message)

async def ocr_parse_resume_task(
    resume_id: str,
    task_id: str,
):
    cache: HRCache = get_cache_instance()
    stage = "starting"
    job_id: str | None = None

    async def set_stage(next_stage: str):
        nonlocal stage
        stage = next_stage

        await cache.set_task_info(TaskInfoSchema(task_id=task_id,status="pending",stage=stage,))
    try:
        await set_stage("loading_resume")
        async with AsyncSessionFactory() as session:
            async with session.begin():
                resume_repo = ResumeRepo(session=session)
                resume = await resume_repo.get_by_id(resume_id)

        if resume is None:
            raise ValueError(f"简历不存在：{resume_id}")

        await set_stage("building_file_path")
        file_path = os.path.join(settings.RESUME_DIR, resume.file_path)

        await set_stage("uploading_resume_to_ocr")
        paddle_ocr = PaddleOcr()
        job_id = await paddle_ocr.create_job(file_path)

        await set_stage("polling_ocr_job")
        jsonl_url = await paddle_ocr.poll_for_state(job_id)

        await set_stage("downloading_ocr_result")
        contents = await paddle_ocr.fetch_parsed_contents(jsonl_url)

        await set_stage("building_result")
        content = "\n\n".join(contents)

        candidate_info: AgentCandidateSchema = await extract_candidate_info(content)
        await cache.set_task_info(TaskInfoSchema(task_id=task_id,status="done",stage="completed",result=candidate_info))
    except Exception as e:
        # PyCharm 控制台会打印完整调用栈和具体代码行
        logger.exception(
            f"OCR任务失败：task_id={task_id}, stage={stage}, job_id={job_id}"
        )
        # APIFox 中保存简洁的错误信息
        error_parts = [
            f"stage={stage}",
            f"exception={type(e).__name__}",
            f"message={e!s}",
        ]

        if job_id:
            error_parts.append(f"job_id={job_id}")
        await cache.set_task_info(TaskInfoSchema(task_id=task_id,status="failed",stage=stage,error=" | ".join(error_parts),))