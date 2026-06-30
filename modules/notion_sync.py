"""
Notion 同步模块 —— 每日日报自动推送到 Notion
在指定父页面下创建每日子页面
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

NOTION_API_VERSION = "2022-06-28"


def create_daily_page(
    token: str,
    page_id: str,
    ai_news: list[dict],
    stories: list[dict],
) -> Optional[str]:
    """
    在 Notion 父页面下创建每日日报子页面

    Args:
        token: Notion Internal Integration Secret
        page_id: 父页面 ID（从 URL p/ 后面获取，32位）
        ai_news: AI 快讯列表
        stories: 古代故事列表

    Returns:
        创建的页面 URL，失败返回 None
    """
    if not token or not page_id:
        logger.warning("Notion 配置不完整，跳过同步")
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    today_cn = datetime.now().strftime("%Y年%m月%d日")

    # 清理 page_id（去除可能的空白字符）
    page_id = page_id.strip().replace("-", "")
    if len(page_id) < 32:
        logger.error(f"Notion page_id 格式不对（长度{len(page_id)}，需要32位）: {page_id}")
        return None

    # 确保 32 位 UUID 格式（纯十六进制）
    page_id = page_id[:32]

    # ── 构建页面内容 ──
    children = _build_page_blocks(ai_news, stories, today_cn)

    # ── 调用 Notion API ──
    try:
        import httpx

        url = "https://api.notion.com/v1/pages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json",
        }

        body = {
            "parent": {
                "type": "page_id",
                "page_id": page_id,
            },
            "properties": {
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": f"📬 {today_cn} 每日双拼日报"
                            }
                        }
                    ]
                }
            },
            "children": children,
        }

        resp = httpx.post(url, headers=headers, json=body, timeout=30)

        if resp.status_code == 200:
            page_data = resp.json()
            notion_id = page_data["id"].replace("-", "")
            page_url = f"https://notion.so/{notion_id}"
            logger.info(f"✓ Notion 同步成功 → {page_url}")
            return page_url
        else:
            logger.error(f"✗ Notion API 错误 [{resp.status_code}]: {resp.text[:500]}")

            # 友好的错误提示
            if "page_id" in resp.text and "validation_error" in resp.text:
                logger.error("  可能原因：1) page_id 格式不对  2) 没有把 qclaw 集成添加到页面 Connections")
            elif "Unauthorized" in resp.text:
                logger.error("  可能原因：NOTION_TOKEN 无效或过期")

            return None

    except Exception as e:
        logger.error(f"✗ Notion 同步失败: {e}")
        return None


def _build_page_blocks(
    ai_news: list[dict],
    stories: list[dict],
    today_cn: str,
) -> list[dict]:
    """构建 Notion 页面的 blocks"""
    blocks = []

    # ── 页面顶部简介 ──
    blocks.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [
                {"type": "text", "text": {"content": f"🤖 AI 快讯 {len(ai_news)} 条  ·  🏯 古代故事 {len(stories)} 则  ·  {today_cn} 自动生成"}}
            ],
            "icon": {"emoji": "📬"},
            "color": "purple_background",
        }
    })

    # ═══════════ AI 快讯板块 ═══════════
    if ai_news:
        blocks.append({"object": "block", "type": "divider", "divider": {}})
        blocks.append({
            "object": "block",
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"type": "text", "text": {"content": f"🤖 AI 快讯 · 今日必读 ({len(ai_news)} 条)"}}]
            }
        })

        for i, item in enumerate(ai_news, 1):
            stars = "★" * int(item.get("score", 3))
            source = item.get("source", "")
            news_url = item.get("url", "")

            # 标题 (H3)
            title_text = f"{i}. {item.get('title', '')}  {stars}"
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": title_text}}]
                }
            })

            # 摘要
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": item.get("summary_zh", "")}}]
                }
            })

            # 来源 + 链接
            link_text = []
            if source:
                link_text.append({"type": "text", "text": {"content": f"📌 {source}"}})
            if news_url:
                if link_text:
                    link_text.append({"type": "text", "text": {"content": "  ·  "}})
                link_text.append({"type": "text", "text": {"content": "🔗 原文", "link": {"url": news_url}}})
            if link_text:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": link_text}
                })

    # ═══════════ 中国古代故事板块 ═══════════
    if stories:
        blocks.append({"object": "block", "type": "divider", "divider": {}})
        blocks.append({
            "object": "block",
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"type": "text", "text": {"content": f"🏯 中国古代故事 · 典故 · 天文地理 ({len(stories)} 则)"}}]
            }
        })

        for i, story in enumerate(stories, 1):
            title = story.get("title", "")
            dynasty = story.get("dynasty", "")
            category = story.get("category", "")
            source = story.get("source", "")
            story_text = story.get("story_zh", "")
            lesson = story.get("lesson", "")
            fun_fact = story.get("fun_fact", "")
            links = story.get("_links", [])

            # 折叠块标题
            toggle_title = f"{i}. {title}"
            if dynasty:
                toggle_title += f"  ·  {dynasty}"
            if category:
                toggle_title += f"  ·  {category}"

            toggle_children = []

            # 出处
            if source:
                toggle_children.append({
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "rich_text": [{"type": "text", "text": {"content": f"📖 出处：{source}"}}],
                        "icon": {"emoji": "📖"},
                        "color": "brown_background",
                    }
                })

            # 故事内容
            toggle_children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": story_text[:2000]}}]
                }
            })

            # 寓意
            if lesson:
                toggle_children.append({
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "rich_text": [{"type": "text", "text": {"content": f"💡 {lesson}"}}],
                        "icon": {"emoji": "💡"},
                        "color": "yellow_background",
                    }
                })

            # 冷知识
            if fun_fact:
                toggle_children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": f"📎 {fun_fact}"}}]
                    }
                })

            # 百度百科链接
            if links:
                link_rich = [{"type": "text", "text": {"content": "🔗 深入了解： "}}]
                for j, (text, url) in enumerate(links):
                    if j > 0:
                        link_rich.append({"type": "text", "text": {"content": "  ·  "}})
                    link_rich.append({"type": "text", "text": {"content": text, "link": {"url": url}}})
                toggle_children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": link_rich}
                })

            # 折叠块
            blocks.append({
                "object": "block",
                "type": "toggle",
                "toggle": {
                    "rich_text": [{"type": "text", "text": {"content": toggle_title}}],
                    "children": toggle_children,
                }
            })

    return blocks
