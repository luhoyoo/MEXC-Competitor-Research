"""云端 AI 研究 agent。

读取当天的"任务单"（brief）和上一份正式报告（如果有），调用 OpenAI Responses API
配合 web_search 工具自动上网搜索、写报告，输出符合任务单要求的精简版日报。

环境变量：
- OPENAI_API_KEY      必填
- OPENAI_RESEARCH_MODEL  可选，默认 gpt-4.1-mini

输出：
- reports/YYYY-MM-DD-web3-product-visual-trend-report.md
"""

from __future__ import annotations

import argparse
import os
from datetime import date, datetime
from pathlib import Path

from .agent_brief import find_previous_report

DEFAULT_MODEL = "gpt-4.1-mini"

SYSTEM_PROMPT = """你是一个给平面设计部门主管服务的 Web3 竞品产品与视觉趋势研究员。

执行规则：
1. 严格按用户消息中的"任务单"要求写报告，不要偏题。
2. 必须主动用 web_search 工具搜索最近 2-7 天的真实公开网络信息；不要编造链接或事实。
3. 只引用真实可访问的官方公告、产品页、博客等链接；找不到证据宁可减少结论，不要虚构。
4. 输出严格遵守任务单里"最终报告结构"段落定义的章节顺序、字数限制和禁止事项。
5. 中文写作，语气克制，信息密度高。
6. 全文输出 Markdown 纯文本，不要包裹任何代码块（如 ```markdown），直接以 H1 开头。
7. 不要写"以下是报告"、"作为 AI 模型..."这类前导语；H1 行就是输出第一行。
"""


def generate_report(
    brief_path: Path,
    final_report_path: Path,
    previous_report_path: Path | None = None,
    model: str | None = None,
) -> Path:
    """根据任务单 + 上一份报告（可选），调 OpenAI 写出今天的正式报告。"""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "未配置 OPENAI_API_KEY。请在 .env 或 GitHub Secrets 中填入 OpenAI API Key。"
        )
    if not brief_path.exists():
        raise FileNotFoundError(f"找不到任务单：{brief_path}")

    brief_text = brief_path.read_text(encoding="utf-8")
    previous_text: str | None = None
    if previous_report_path and previous_report_path.exists():
        previous_text = previous_report_path.read_text(encoding="utf-8")

    user_content = brief_text
    if previous_text:
        user_content += (
            "\n\n---\n\n"
            "下面是上一份正式报告（作为对照基线，不要原样照抄；只用于判断变化、强化、减弱）：\n\n"
            + previous_text
        )

    # 延迟导入，避免在没装 openai 时模块加载失败
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    chosen_model = model or os.environ.get("OPENAI_RESEARCH_MODEL", DEFAULT_MODEL)

    response = client.responses.create(
        model=chosen_model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        tools=[{"type": "web_search"}],
        max_output_tokens=8000,
    )

    report_text = (response.output_text or "").strip()
    if not report_text:
        raise RuntimeError("OpenAI 返回为空，请检查 API Key、模型可用性或网络。")

    # 如果模型仍然给了 ```markdown 包装，剥掉
    if report_text.startswith("```"):
        lines = report_text.splitlines()
        # 去掉首行 ``` 和尾行 ```
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        report_text = "\n".join(lines).strip()

    final_report_path.parent.mkdir(parents=True, exist_ok=True)
    final_report_path.write_text(report_text + "\n", encoding="utf-8")
    return final_report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="云端 AI 研究 agent：读任务单 → 写正式报告")
    parser.add_argument("--date", dest="run_date", help="日期，YYYY-MM-DD；不填用今天")
    parser.add_argument("--reports-dir", default="reports", help="报告目录")
    parser.add_argument("--model", help="覆盖模型名（默认 gpt-4.1-mini）")
    args = parser.parse_args()

    report_date = args.run_date or date.today().isoformat()
    # 校验日期格式
    datetime.strptime(report_date, "%Y-%m-%d")

    reports_dir = Path(args.reports_dir)
    brief_path = reports_dir / f"{report_date}-codex-ai-research-brief.md"
    final_report_path = reports_dir / f"{report_date}-web3-product-visual-trend-report.md"
    previous_report_path = find_previous_report(reports_dir, report_date)

    out = generate_report(
        brief_path=brief_path,
        final_report_path=final_report_path,
        previous_report_path=previous_report_path,
        model=args.model,
    )
    print(f"[done] 正式报告已生成：{out.resolve()}")


if __name__ == "__main__":
    main()
