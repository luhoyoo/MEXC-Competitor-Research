"""把日报推送到飞书/Lark 群组的自定义机器人 Webhook。

功能：
- 默认模式：把整份 Markdown 报告内容塞进卡片（5 分钟阅读量内）
- summary 模式：只发 TL;DR 三行
- 卡片底部带「查看完整报告」按钮，跳转到飞书文档或 GitHub 链接
- 支持 Webhook 签名（可选，由群机器人配置决定）

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

# Lark/飞书卡片单个 lark_md 元素文本上限约 30000 字符，留出余量
MAX_CARD_BODY_CHARS = 28000


def notify_group(
    report_path: Path,
    config_path: Path,
    run_date: str | None = None,
    doc_url: str | None = None,
    fallback_url: str | None = None,
    mode: str = "full",
) -> dict[str, Any]:
    """把日报推送到群机器人。返回飞书接口的响应 payload。

    mode:
        - full    : 卡片包含 TL;DR + 完整报告内容（默认）
        - summary : 卡片只包含 TL;DR 三行
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
    template = webhook_cfg.get("card_template", "blue")

    parsed_title, body = extract_title_and_body(markdown)
    card_title = f"{title_prefix} · {report_date}"
    tldr = extract_tldr(markdown)

    if mode == "summary":
        card = build_summary_card(
            title=card_title,
            tldr=tldr,
            template=template,
        )
    else:
        card = build_full_card(
            title=card_title,
            tldr=tldr,
            body_markdown=body,
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
                "mode": mode,
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


def extract_title_and_body(markdown: str) -> tuple[str | None, str]:
    """把第一个 H1 标题和正文分开。"""
    lines = markdown.splitlines()
    title: str | None = None
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            body_start = i + 1
            break
    body = "\n".join(lines[body_start:]).strip()
    return title, body


def extract_tldr(markdown: str) -> dict[str, str]:
    """从 Markdown 报告里抓 TL;DR 三行。

    匹配新版报告格式：
        - 🎨 视觉：...
        - 📦 产品：...
        - ✅ MEXC 行动：...

    任何字段抓不到都返回占位提示，不会让推送中断。
    """
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


def truncate_body(body: str, limit: int = MAX_CARD_BODY_CHARS) -> str:
    if len(body) <= limit:
        return body
    return body[: limit - 30].rstrip() + "\n\n…（内容过长已截断，请点按钮看完整报告）"


# ---------- 卡片构造 ----------


def build_full_card(
    title: str,
    tldr: dict[str, str],
    body_markdown: str,
    template: str = "blue",
) -> dict[str, Any]:
    """完整卡片：顶部 TL;DR 30 秒读完 + 分隔线 + 完整报告正文。无外部链接。"""
    tldr_block = (
        "**🎯 TL;DR · 30 秒读完**\n\n"
        f"**🎨 视觉**：{tldr['visual']}\n\n"
        f"**📦 产品**：{tldr['product']}\n\n"
        f"**✅ MEXC 行动**：{tldr['action']}"
    )
    body = truncate_body(body_markdown.strip(), MAX_CARD_BODY_CHARS - len(tldr_block) - 200)

    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": tldr_block},
        },
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**📄 完整报告**\n\n{body}"},
        },
    ]
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": template,
        },
        "elements": elements,
    }


def build_summary_card(
    title: str,
    tldr: dict[str, str],
    template: str = "blue",
) -> dict[str, Any]:
    """精简卡片：仅 TL;DR 三行。"""
    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**🎨 视觉**\n{tldr['visual']}\n\n"
                    f"**📦 产品**\n{tldr['product']}\n\n"
                    f"**✅ MEXC 行动**\n{tldr['action']}"
                ),
            },
        }
    ]
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": template,
        },
        "elements": elements,
    }


# 兼容旧函数名
def build_card(
    title: str,
    tldr: dict[str, str],
    button_text: str = "",  # noqa: ARG001 - 保留签名兼容
    button_url: str | None = None,  # noqa: ARG001
    template: str = "blue",
) -> dict[str, Any]:
    return build_summary_card(title, tldr, template)


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
    parser = argparse.ArgumentParser(description="把日报推送到飞书/Lark 群机器人")
    parser.add_argument("--report", required=True, help="Markdown 报告路径")
    parser.add_argument("--config", default="config/lark_publish.yaml", help="配置文件")
    parser.add_argument("--date", dest="run_date", help="日期，格式 YYYY-MM-DD")
    parser.add_argument(
        "--mode",
        choices=["full", "summary"],
        default="full",
        help="full=TL;DR + 完整报告（默认），summary=仅 TL;DR",
    )
    args = parser.parse_args()

    response = notify_group(
        report_path=Path(args.report),
        config_path=Path(args.config),
        run_date=args.run_date,
        mode=args.mode,
    )
    print(f"[done] 群消息已推送（mode={args.mode}）：{response}")


if __name__ == "__main__":
    main()
