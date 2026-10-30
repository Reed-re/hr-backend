import os
from langchain_openai import ChatOpenAI


api_key1 = os.getenv("DEEPSEEK_API_KEY")
api_key2 = os.getenv("QWEN_API_KEY")


deepseek_llm = ChatOpenAI(
    model="deepseek-flash",
    base_url="https://api.deepseek.com",
    api_key=api_key1
)

qwen_llm = ChatOpenAI(
    model="qwen3.7-plus",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=api_key2
)

