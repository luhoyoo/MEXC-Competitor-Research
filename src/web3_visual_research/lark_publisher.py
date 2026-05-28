from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from .config import load_yaml


def publish_report_to_lark(
    report_path: Path,
    config_path: Path,
    run_date: str | None = None,
) -> Path:
    report_date = run_date or date.today().isoformat()
    config = load_yaml(config_path.read_text(encoding="utf-8")).get("lark", {})
    if not config.get("enabled", True):
        raise RuntimeError("Lark 发布已关闭：config/lark_publish.yaml 中 enabled=false")

    cli_command = config.get("cli_command", "lark-cli")
    cli_path = resolve_lark_cli(cli_command)
    if not cli_path:
        raise RuntimeError(
            f"没有找到 {cli_command}。请先运行 zsh setup_lark.sh 安装并登录 Lark CLI。"
        )

    if not report_path.exists():
        raise FileNotFoundError(f"找不到报告文件：{report_path}")

    title_prefix = config.get("doc_title_prefix", "Web3 竞品产品与视觉趋势日报")
    title = f"{title_prefix} - {report_date}"
    markdown = report_path.read_text(encoding="utf-8")
    content = f"<title>{title}</title>\n\n{markdown}"

    command = [
        cli_path,
        "docs",
        "+create",
        "--api-version",
        "v2",
        "--doc-format",
        "markdown",
        "--content",
        content,
    ]

    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    output_dir = Path(config.get("output_dir", "data/lark")) / report_date
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "publish-result.json"
    payload: dict[str, Any] = {
        "report_path": str(report_path.resolve()),
        "title": title,
        "command": " ".join(command[:5]) + " ...",
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if result.returncode != 0:
        raise RuntimeError(
            f"Lark 发布失败。详情见 {output_path.resolve()}。\n{result.stderr or result.stdout}"
        )
    return output_path


def resolve_lark_cli(cli_command: str) -> str | None:
    candidates = [
        shutil.which(cli_command),
        str((Path.cwd() / "node_modules" / ".bin" / "lark-cli").resolve()),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="把 Markdown 日报发布到 Lark 文档")
    parser.add_argument("--report", required=True, help="要发布的 Markdown 报告路径")
    parser.add_argument("--config", default="config/lark_publish.yaml", help="Lark 发布配置")
    parser.add_argument("--date", dest="run_date", help="日期，格式 YYYY-MM-DD")
    args = parser.parse_args()

    output_path = publish_report_to_lark(
        report_path=Path(args.report),
        config_path=Path(args.config),
        run_date=args.run_date,
    )
    print(f"[done] Lark 发布结果已保存：{output_path.resolve()}")


if __name__ == "__main__":
    main()
