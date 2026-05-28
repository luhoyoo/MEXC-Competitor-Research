"""把日报推送到飞书/Lark 群组的自定义机器人 Webhook。

群消息样式：
- 卡片头部：报告标题 + 日期
- 卡片正文：TL;DR 三行（30 秒读完）
- 卡片底部：「查看完整报告」按钮 → 跳转到 Lark 云文档

环境变量：
- LARK_GROUP_WEBHOOK         Webhook URL（必填）
- LARK_GROUP_WEBHOOK_SECRET  可选签名校验密钥
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import time
from datetime import date
from pathlib import Path
from typing import Any
from urllib import error, request

from .config import load_yaml


def notify_group(
    report_path: Path,
    config_path: Path,
    run_date: str | None = None,
    doc_url: str | None = None,
    fallback_url: str | None = None,
) -> dict[str, Any]:
    """把日报 TL;DR 推送到群机器人。返回飞书接口的响应 payload。

    doc_url     : Lark 云文档链接，按钮优先跳这个
    fallback_url: 备用链接（如 GitHub），doc_url 缺失时用
    """
    report_date = run_date or date.today().isoformat()
    config = load_yaml(config_path.read_text(encoding="utf-8")).get("lark", {})
    webhook_cfg = config.get("webhook", {}) or {}

    if not webhook_cfg.get("enabled", True):
        raise RuntimeError("群机器人推送已关闭：lark.webhook.enabled=false")

    webhook_url = os.environ.get(
        webhook_cfg.get("env_url", "LARK_GROUP_WEBHOOK"),
        "",
    ).strip()
    if not webhook_url:
        raise RuntimeError(
            "没有找到 Webhook URL。请在环境变量 LARK_GROUP_WEBHOOK 里填入群机器人 URL。"
        )
    secret = os.environ.get(
        webhook_cfg.get("env_secret", "LARK_GROUP_WEBHOOK_SECRET"),
        "",
    ).strip()

    if not report_path.exists():
        raise FileNotFoundError(f"找不到报告文件：{report_path}")

    markdown = report_path.read_text(encoding="utf-8")
    title_prefix = webhook_cfg.get("title_prefix", "Web3 竞品产品与视觉趋势日报")
    button_text = webhook_cfg.get("button_text", "查看完整报告")
    template = webhook_cfg.get("card_template", "blue")
    link_url = doc_url or fallback_url
    tldr = extract_tldr(markdown)

    card = build_card(
        title=f"{title_prefix} · {report_date}",
        tldr=tldr,
        button_text=button_text,
        button_url=link_url,
        template=template,
    )
    payload: dict[str, Any] = {"msg_type": "interactive", "card": card}

    if secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = sign_webhook(timestamp, secret)

    response = post_webhook(webhook_url, payload)

    output_dir = Path(config.get("output_dir", "data/lark")) / report_date
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "chat-notify-result.json"
    output_path.write_text(
        json.dumps(
            {
                "report_path": str(report_path.resolve()),
                "doc_url": doc_url,
                "fallback_url": fallback_url,
                "link_used": link_url,
                "response": response,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if response.get("code") not in (0, None):
        raise RuntimeError(f"群消息推送失败：{response}")
    return response


# ---------- 报告解析 ----------


def extract_tldr(markdown: str) -> dict[str, str]:
    visual = _find_line(markdown, r"🎨\s*视觉[:：]\s*(.+)")
    product = _find_line(markdown, r"📦\s*产品[:：]\s*(.+)")
    action = _find_line(markdown, r"✅\s*MEXC\s*行动[:：]\s*(.+)")
    return {
        "visual": visual or "（未识别到视觉摘要，请打开完整报告查看）",
        "product": product or "（未识别到产品摘要，请打开完整报告查看）",
        "action": action or "（未识别到 MEXC 行动建议，请打开完整报告查看）",
    }


def _find_line(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text)
    if not match:
        return None
    line = match.group(1).strip()
    line = re.sub(r"\*+$", "", line).strip()
    return line


# ---------- 卡片构造 ----------


def build_card(
    title: str,
    tldr: dict[str, str],
    button_text: str,
    button_url: str | None,
    template: str = "blue",
) -> dict[str, Any]:
    """TL;DR 卡片：30 秒读完 + 跳转按钮。"""
    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    "**🎯 TL;DR · 30 秒读完**\n\n"
                    f"**🎨 视觉**：{tldr['visual']}\n\n"
                    f"**📦 产品**：{tldr['product']}\n\n"
                    f"**✅ MEXC 行动**：{tldr['action']}"
                ),
            },
        }
    ]
    if button_url:
        elements.append({"tag": "hr"})
        elements.append(
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": button_text},
                        "type": "primary",
                        "url": button_url,
                    }
                ],
            }
        )
    else:
        elements.append(
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": "⚠️ Lark 文档生成失败，请联系管理员",
                    }
                ],
            }
        )
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": template,
        },
        "elements": elements,
    }


# ---------- 签名 + 发送 ----------


def sign_webhook(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def post_webhook(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Webhook HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Webhook 网络错误：{exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


# ---------- CLI ----------


def main() -> None:
    parser = argparse.ArgumentParser(description="把日报 TL;DR 推送到飞书/Lark 群")
    parser.add_argument("--report", required=True, help="Markdown 报告路径")
    parser.add_argument("--config", default="config/lark_publish.yaml")
    parser.add_argument("--date", dest="run_date")
    parser.add_argument("--doc-url", dest="doc_url", help="Lark 文档 URL")
    parser.add_argument("--fallback-url", dest="fallback_url", help="备用 URL")
    args = parser.parse_args()

    response = notify_group(
        report_path=Path(args.report),
        config_path=Path(args.config),
        run_date=args.run_date,
        doc_url=args.doc_url,
        fallback_url=args.fallback_url,
    )
    print(f"[done] 群消息已推送：{response}")


if __name__ == "__main__":
    main()
