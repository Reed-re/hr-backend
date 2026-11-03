import json
import os
from typing import List

from settings import settings
import httpx
import asyncio
from loguru import logger
class PaddleOcr:
    def __init__(self):
        self.job_url = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
        self.access_token = settings.PADDLE_OCR_ACCESS_TOKEN
        self.model_name = "PaddleOCR-VL-1.5"
        self.timeout = httpx.Timeout(
            connect=10.0,
            read=120.0,
            write=120.0,
            pool=10.0,
        )
        self.headers = {
            "Authorization": f"bearer {self.access_token}",
        }
        self.optional_payload = {
            "useDocOrientationClassify": False,
            "useDocUnwarping": False,
            "useChartRecognition": False,
        }

    async def _post_job_with_retry(
            self,
            *,
            json_payload=None,
            form_data=None,
            file_path=None,
            max_retries=5,
    ):
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if file_path is not None:
                        with open(file_path, "rb") as fp:
                            response = await client.post(
                                self.job_url,
                                headers=self.headers,
                                data=form_data,
                                files={"file": fp},
                            )
                    else:
                        response = await client.post(
                            self.job_url,
                            headers=self.headers,
                            json=json_payload,
                        )

                if response.status_code < 500:
                    return response

                last_error = ValueError(
                    f"PaddleOCR返回状态码：{response.status_code}"
                )
            except (
                    httpx.ConnectTimeout,
                    httpx.ReadTimeout,
                    httpx.ConnectError,
            ) as exc:
                last_error = exc

            logger.warning(
                "PaddleOCR上传失败，第{}次：{}",
                attempt,
                last_error,
            )

            if attempt < max_retries:
                await asyncio.sleep(min(2 ** attempt, 30))

        raise last_error

    async def create_job(self, file: str) -> str:
        if file.startswith("http"):
            self.headers["Content-Type"] = "application/json"
            payload = {
                "fileUrl": file,
                "model": self.model_name,
                "optionalPayload": self.optional_payload,
            }
            job_resp = await self._post_job_with_retry(
                json_payload=payload,
            )
        else:
            if not os.path.exists(file):
                raise ValueError(f"错误：{file}不存在！")

            data = {
                "model": self.model_name,
                "optionalPayload": json.dumps(self.optional_payload),
            }
            job_resp = await self._post_job_with_retry(
                form_data=data,
                file_path=file,
            )

        if job_resp.status_code != 200:
            logger.error(f"文件上传失败：{job_resp.text}, file: {file}")
            raise ValueError(f"文件上传失败：{job_resp.text}")

        return job_resp.json()["data"]["jobId"]

    async def poll_for_state(self, job_id: str) -> str | None:
        network_errors = 0
        url = f"{self.job_url}/{job_id}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:
                try:
                    job_result_response = await client.get(
                        url,
                        headers=self.headers,
                    )
                    network_errors = 0
                except (
                        httpx.ConnectTimeout,
                        httpx.ReadTimeout,
                        httpx.ConnectError,
                ) as exc:
                    network_errors += 1
                    logger.warning(
                        "OCR轮询连接失败，job_id={}，第{}次：{}",
                        job_id,
                        network_errors,
                        exc,
                    )

                    if network_errors >= 10:
                        raise

                    await asyncio.sleep(min(2 ** network_errors, 30))
                    continue

                if job_result_response.status_code == 200:
                    result_data = job_result_response.json()["data"]
                    state = result_data["state"]

                    if state == "pending":
                        logger.info(f"{job_id} pending...")
                    elif state == "running":
                        try:
                            progress = result_data["extractProgress"]
                            logger.info(
                                "任务：{}运行中，{}/{}",
                                job_id,
                                progress["extractedPages"],
                                progress["totalPages"],
                            )
                        except KeyError:
                            logger.info("OCR任务运行中...")
                    elif state == "done":
                        progress = result_data["extractProgress"]
                        logger.info(
                            "任务{}完成，提取{}页",
                            job_id,
                            progress["extractedPages"],
                        )
                        return result_data["resultUrl"]["jsonUrl"]
                    elif state == "failed":
                        raise ValueError(result_data["errorMsg"])
                else:
                    raise ValueError(
                        f"获取任务 {job_id} 状态错误："
                        f"{job_result_response.status_code}"
                    )

                await asyncio.sleep(2)

    async def fetch_parsed_contents(self, jsonl_url: str) -> List[str]:
        contents = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            jsonl_response = await client.get(jsonl_url)
            if jsonl_response.status_code != 200:
                raise ValueError(f"获取内容失败：{jsonl_response.text}")
            lines = jsonl_response.text.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                result = json.loads(line)["result"]
                for res in result["layoutParsingResults"]:
                    contents.append(res["markdown"]["text"])
        return contents