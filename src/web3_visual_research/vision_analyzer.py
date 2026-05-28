from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


ANALYSIS_PROMPT = """
你是给 Web3 交易所平面设计主管服务的视觉趋势分析助手。
请只分析这张公开营销图片的视觉设计，不要做投资建议，不要分析交易数据。

请用中文输出严格 JSON，字段如下：
{
  "visual_type": "官网首页Banner / 活动页KV / App-Web推广图 / Blog-Academy封面图 / 社媒宣传图 / 公告配图 / 其他",
  "main_colors": ["颜色1", "颜色2", "颜色3"],
  "style_tags": ["3D", "科技感", "插画", "人物", "极简", "赛博", "金融感"],
  "layout": "版式结构分析，说明主体、标题、CTA、留白和视觉重心",
  "copy_hierarchy": "标题文案层级分析",
  "visual_elements": ["币种", "金币", "卡片", "手机", "火箭", "排行榜", "奖杯"],
  "brand_asset_usage": "品牌色、Logo、字体、品牌图形资产的使用方式",
  "campaign_type": "节日 / 交易赛 / Launchpool / 空投 / 新币上线 / 产品推广 / 教育内容 / 其他",
  "design_highlights": "设计亮点，偏审美和转化表达",
  "reference_points": "可借鉴点，给设计团队的具体启发",
  "risk_notes": "与 MEXC 品牌可能冲突、容易同质化或需要谨慎跟进的地方"
}
""".strip()


def analyze_image(image_path: Path, skip_vision: bool = False) -> dict[str, Any]:
    if skip_vision:
        return fallback_analysis("已跳过 AI 视觉分析。配置 MiniMax Key 后可运行 zsh run_daily.sh 生成完整视觉分析。")

    provider = os.getenv("VISION_PROVIDER", "minimax").strip().lower()
    if provider == "minimax":
        return analyze_image_with_minimax(image_path)
    if provider == "openai":
        return analyze_image_with_openai(image_path)
    return fallback_analysis(f"未知视觉分析服务：{provider}。请把 VISION_PROVIDER 设置为 minimax 或 openai。")


def analyze_image_with_openai(image_path: Path) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return fallback_analysis("未检测到 OPENAI_API_KEY，本次仅归档图片，未做 AI 视觉分析。")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini")
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": ANALYSIS_PROMPT},
                        {
                            "type": "input_image",
                            "image_url": image_to_data_url(image_path),
                            "detail": "auto",
                        },
                    ],
                }
            ],
        )
        text = response.output_text.strip()
        return parse_json_response(text)
    except Exception as exc:
        return fallback_analysis(f"OpenAI 视觉分析失败：{exc}")


def analyze_image_with_minimax(image_path: Path) -> dict[str, Any]:
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        return fallback_analysis("未检测到 MINIMAX_API_KEY，本次仅归档图片，未做 MiniMax 视觉分析。")

    mmx_path = shutil.which("mmx")
    if not mmx_path:
        return fallback_analysis("未检测到 MiniMax CLI：请先运行 zsh setup_minimax.sh，再重新生成日报。")

    prompt = os.getenv("MINIMAX_VISION_PROMPT", ANALYSIS_PROMPT)
    timeout = int(os.getenv("MINIMAX_VISION_TIMEOUT", "120"))
    env = os.environ.copy()
    env["MINIMAX_API_KEY"] = api_key
    commands = [
        [mmx_path, "vision", "describe", "--image", str(image_path), "--prompt", prompt],
        [mmx_path, "vision", "describe", str(image_path), "--prompt", prompt],
    ]
    result = None
    for command in commands:
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return fallback_analysis("MiniMax 视觉分析超时，请稍后重试或调大 MINIMAX_VISION_TIMEOUT。")
        except Exception as exc:
            return fallback_analysis(f"MiniMax 视觉分析启动失败：{exc}")

        combined = f"{result.stdout}\n{result.stderr}".lower()
        if result.returncode == 0 or ("unknown option" not in combined and "unexpected argument" not in combined):
            break

    output = (result.stdout or "").strip() if result else ""
    error = (result.stderr or "").strip() if result else ""
    if result.returncode != 0:
        message = error or output or f"mmx 退出码 {result.returncode}"
        return fallback_analysis(f"MiniMax 视觉分析失败：{message}")

    try:
        return parse_json_response(output)
    except Exception:
        return normalize_minimax_text_response(output)


def image_to_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/jpeg")
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("AI 返回内容不是 JSON 对象")
    return data


def normalize_minimax_text_response(text: str) -> dict[str, Any]:
    analysis = fallback_analysis("MiniMax 已返回分析，但不是标准 JSON，已先保存为设计观察文本。")
    analysis["visual_type"] = "社媒宣传图"
    analysis["design_highlights"] = text[:1200] if text else "MiniMax 未返回可读分析内容。"
    analysis["reference_points"] = "建议查看上方 MiniMax 分析文本，并在下一版提示词中继续收敛为结构化 JSON。"
    return analysis


def fallback_analysis(note: str) -> dict[str, Any]:
    return {
        "visual_type": "待识别",
        "main_colors": [],
        "style_tags": [],
        "layout": "待分析",
        "copy_hierarchy": "待分析",
        "visual_elements": [],
        "brand_asset_usage": "待分析",
        "campaign_type": "待识别",
        "design_highlights": note,
        "reference_points": "建议补充 AI 视觉分析后再进入设计复盘。",
        "risk_notes": "暂无明确风险判断。",
    }
