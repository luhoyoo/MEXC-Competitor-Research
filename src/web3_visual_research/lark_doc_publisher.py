"""把日报发布为 Lark/飞书云文档（Docs v2，import_task API）。

API 路径：
1. POST /open-apis/auth/v3/tenant_access_token/internal  → 拿 tenant_access_token
2. POST /open-apis/drive/v1/medias/upload_all          → 把 .md 当 docx 文件上传
3. POST /open-apis/docx/v1/documents/{file_token}/raw_content  （备用，不需要）

实际更稳的方式是用 import_task API：
1. tenant_access_token
2. POST /open-apis/drive/v1/import_tasks  → 提交 markdown 转换任务
3. GET  /open-apis/drive/v1/import_tasks/{ticket}  → 轮询直到拿到 doc_token
4. 拼出可访问 URL：https://{domain}/docx/{doc_token}

环境变量：
- LARK_APP_ID         必填，自建应用的 App ID
- LARK_APP_SECRET     必填，自建应用的 App Secret
- LARK_DOMAIN         可选，默认 open.larksuite.com（国际版）；国内用 open.feishu.cn
- LARK_DOC_FOLDER_TOKEN  可选，把文档放到指定文件夹

输出：
- 返回 doc_url，可直接在浏览器/Lark 内打开
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib import error, request

DEFAULT_DOMAIN = "open.larksuite.com"


class LarkDocPublishError(RuntimeError):
    pass


def publish_markdown_as_doc(
    markdown_path: Path,
    doc_title: str,
    folder_token: str | None = None,
) -> str:
    """把 markdown 文件转成 Lark 云文档，返回可访问的 URL。"""
    app_id = os.environ.get("LARK_APP_ID", "").strip()
    app_secret = os.environ.get("LARK_APP_SECRET", "").strip()
    domain = os.environ.get("LARK_DOMAIN", DEFAULT_DOMAIN).strip() or DEFAULT_DOMAIN
    folder = (folder_token or os.environ.get("LARK_DOC_FOLDER_TOKEN", "")).strip()

    if not app_id or not app_secret:
        raise LarkDocPublishError(
            "LARK_APP_ID / LARK_APP_SECRET 未配置，无法创建 Lark 文档。"
            "请在 Lark 开放平台创建自建应用并配置 docs:document、drive:drive 权限。"
        )
    if not markdown_path.exists():
        raise FileNotFoundError(f"找不到 markdown 文件：{markdown_path}")

    token = _get_tenant_access_token(domain, app_id, app_secret)
    md_bytes = markdown_path.read_bytes()
    file_token = _upload_markdown(domain, token, doc_title, md_bytes, folder)
    ticket = _create_import_task(domain, token, file_token, doc_title, folder)
    doc_token, doc_url = _wait_for_import(domain, token, ticket)
    if not doc_url:
        # API 没有直接返回 url 时自己拼一个；不同租户域名不同
        doc_url = f"https://{domain.replace('open.', '')}/docx/{doc_token}"
    return doc_url


# ---------- internals ----------


def _get_tenant_access_token(domain: str, app_id: str, app_secret: str) -> str:
    url = f"https://{domain}/open-apis/auth/v3/tenant_access_token/internal"
    body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8")
    resp = _http_json("POST", url, body=body, headers={"Content-Type": "application/json"})
    if resp.get("code") != 0:
        raise LarkDocPublishError(f"获取 tenant_access_token 失败：{resp}")
    token = resp.get("tenant_access_token")
    if not token:
        raise LarkDocPublishError(f"返回里没有 tenant_access_token：{resp}")
    return token


def _upload_markdown(
    domain: str,
    token: str,
    doc_title: str,
    md_bytes: bytes,
    folder: str,
) -> str:
    url = f"https://{domain}/open-apis/drive/v1/medias/upload_all"
    file_name = f"{doc_title}.md"
    boundary = "----WebKitFormBoundaryLark" + str(int(time.time()))
    parts: list[bytes] = []

    def _add_field(name: str, value: str) -> None:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(value.encode("utf-8"))
        parts.append(b"\r\n")

    _add_field("file_name", file_name)
    _add_field("parent_type", "ccm_import_open")
    _add_field("parent_node", folder or "")
    _add_field("size", str(len(md_bytes)))
    _add_field("extra", json.dumps({"obj_type": "docx", "file_extension": "md"}))

    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'.encode()
    )
    parts.append(b"Content-Type: text/markdown\r\n\r\n")
    parts.append(md_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())

    body = b"".join(parts)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    resp = _http_json("POST", url, body=body, headers=headers)
    if resp.get("code") != 0:
        raise LarkDocPublishError(f"上传 markdown 失败：{resp}")
    file_token = (resp.get("data") or {}).get("file_token")
    if not file_token:
        raise LarkDocPublishError(f"返回里没有 file_token：{resp}")
    return file_token


def _create_import_task(
    domain: str,
    token: str,
    file_token: str,
    doc_title: str,
    folder: str,
) -> str:
    url = f"https://{domain}/open-apis/drive/v1/import_tasks"
    payload = {
        "file_extension": "md",
        "file_token": file_token,
        "type": "docx",
        "file_name": doc_title,
        "point": {
            "mount_type": 1,  # 1 = 我的空间或指定文件夹
            "mount_key": folder or "",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = _http_json("POST", url, body=body, headers=headers)
    if resp.get("code") != 0:
        raise LarkDocPublishError(f"创建 import_task 失败：{resp}")
    ticket = (resp.get("data") or {}).get("ticket")
    if not ticket:
        raise LarkDocPublishError(f"返回里没有 ticket：{resp}")
    return ticket


def _wait_for_import(
    domain: str,
    token: str,
    ticket: str,
    max_attempts: int = 30,
    sleep_seconds: float = 1.0,
) -> tuple[str, str]:
    url = f"https://{domain}/open-apis/drive/v1/import_tasks/{ticket}"
    headers = {"Authorization": f"Bearer {token}"}
    last: dict[str, Any] = {}
    for _ in range(max_attempts):
        resp = _http_json("GET", url, headers=headers)
        if resp.get("code") != 0:
            raise LarkDocPublishError(f"查询 import_task 失败：{resp}")
        last = (resp.get("data") or {}).get("result") or {}
        job_status = last.get("job_status")
        # 0 = 成功；其他非 0 大多数是中间状态或错误码
        if job_status == 0:
            doc_token = last.get("token") or ""
            doc_url = last.get("url") or ""
            return doc_token, doc_url
        # 常见进行中状态码：1（处理中）、2（排队中）；其他值视为失败
        if job_status not in (None, 1, 2, 3):
            raise LarkDocPublishError(f"import_task 失败：{last}")
        time.sleep(sleep_seconds)
    raise LarkDocPublishError(f"import_task 超时未完成。最近一次响应：{last}")


def _http_json(
    method: str,
    url: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    req = request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LarkDocPublishError(f"HTTP {exc.code} {url}: {detail}") from exc
    except error.URLError as exc:
        raise LarkDocPublishError(f"网络错误 {url}: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


# ---------- CLI ----------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="把 markdown 报告发布为 Lark 文档")
    parser.add_argument("--report", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--folder", default="", help="可选，目标文件夹 token")
    args = parser.parse_args()

    url = publish_markdown_as_doc(Path(args.report), args.title, args.folder or None)
    print(url)


if __name__ == "__main__":
    main()


# 让外部知道这两个变量含义
__all__ = ["publish_markdown_as_doc", "LarkDocPublishError"]
