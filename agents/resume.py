import asyncio
import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llms import deepseek_llm
from agents.prompts import EXTRACT_CANDIDATE_SYSTEM_PROMPT
from schemas.agent_schema import AgentCandidateSchema


TEXT_FIELDS = (
    "name",
    "birthday",
    "email",
    "phone_number",
    "work_experience",
    "project_experience",
    "education_experience",
    "self_evaluation",
    "other_information",
    "skills",
)


def convert_to_text(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        return value

    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            else:
                parts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(parts)

    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)

    return str(value)


async def extract_candidate_info(content: str) -> AgentCandidateSchema:
    llm = deepseek_llm.bind(
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=2000,
    )

    response = await asyncio.wait_for(
        llm.ainvoke([
            SystemMessage(content=EXTRACT_CANDIDATE_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    "请从下面的简历文本中提取候选人信息，只输出JSON，不要Markdown。"
                    "project_experience、work_experience、education_experience、"
                    "other_information、skills 必须全部输出字符串。"
                    "多个项目或技能不能用数组，请使用换行符连接。"
                    "没有的信息返回null。\n\n"
                    f"{content[:12000]}"
                )
            ),
        ]),
        timeout=25,
    )

    data = json.loads(response.content)

    for field in TEXT_FIELDS:
        data[field] = convert_to_text(data.get(field))

    return AgentCandidateSchema.model_validate(data)