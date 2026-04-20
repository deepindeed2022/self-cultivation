from __future__ import annotations

import os

from ..utils.http import build_client, post_json
from ..utils.logging import get_logger


log = get_logger(__name__)


def build_card(title: str, markdown_body: str) -> dict:
    """构造飞书交互式卡片 payload（msg_type=interactive）。

    飞书卡片的 lark_md 支持基础 Markdown（链接 / 粗体 / 列表）。
    """
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": markdown_body},
                }
            ],
        },
    }


def send_feishu(title: str, markdown_body: str, *, webhook: str | None = None) -> bool:
    url = webhook or os.getenv("FEISHU_WEBHOOK", "").strip()
    if not url:
        log.warning("FEISHU_WEBHOOK 未配置，跳过推送")
        return False

    payload = build_card(title, markdown_body)
    try:
        with build_client({"Content-Type": "application/json"}) as client:
            resp = post_json(client, url, payload)
    except Exception as e:  # noqa: BLE001
        log.error("飞书推送失败: %s", e)
        return False

    # 飞书成功返回 {"StatusCode":0,"StatusMessage":"success",...} 或 {"code":0,...}
    ok = resp.get("StatusCode") == 0 or resp.get("code") == 0
    if not ok:
        log.error("飞书推送返回异常: %s", resp)
        return False
    log.info("飞书推送成功")
    return True
