from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential


DEFAULT_TIMEOUT = 30.0


class NonRetryableHTTPError(Exception):
    """4xx（非 429）错误包装，携带状态码与响应体片段，便于日志定位。"""

    def __init__(self, status: int, url: str, body: str):
        self.status = status
        self.url = url
        self.body = body
        super().__init__(f"HTTP {status} {url}: {body[:300]}")


def build_client(headers: dict[str, str] | None = None) -> httpx.Client:
    return httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        headers=headers or {},
        follow_redirects=True,
    )


def _should_retry(exc: BaseException) -> bool:
    # 4xx（除 429）不重试
    if isinstance(exc, NonRetryableHTTPError):
        return False
    # 其他网络错误 / 5xx / 429 都值得重试
    return True


_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception(_should_retry),
    reraise=True,
)


def _check(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    status = resp.status_code
    if 400 <= status < 500 and status != 429:
        raise NonRetryableHTTPError(status, str(resp.request.url), resp.text)
    # 429 与 5xx 走重试分支
    resp.raise_for_status()


@_retry
def get_json(client: httpx.Client, url: str, params: dict | None = None) -> dict | list:
    resp = client.get(url, params=params)
    _check(resp)
    return resp.json()


@_retry
def post_json(client: httpx.Client, url: str, payload: dict) -> dict:
    resp = client.post(url, json=payload)
    _check(resp)
    return resp.json()
