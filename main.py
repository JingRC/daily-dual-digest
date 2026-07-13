#!/usr/bin/env python3
"""
每日双拼日报 — 主程序
──────────────────────────
功能：AI快讯聚合 + 中国古代故事典故生成 + Email推送 + 静态站点发布
触发：GitHub Actions 每日定时 / 手动运行

用法：
  python main.py                      # 完整运行
  python main.py --news-only          # 仅AI快讯
  python main.py --stories-only       # 仅古代故事
  python main.py --no-email           # 跳过邮件发送
"""

import argparse
import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote

import yaml
from jinja2 import Template

from modules.ancient_stories import build_stories_prompt, load_history, save_to_history, get_stats
from modules.email_sender import send_daily_email

# ── 日志 ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("daily-digest")

# ── 路径 ──────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent
DOCS_DIR = ROOT_DIR / "docs"
TEMPLATE_DIR = ROOT_DIR / "templates"
CONFIG_PATH = ROOT_DIR / "config.yml"
ENV_PATH = ROOT_DIR / ".env"


def _load_dotenv():
    """加载 .env 文件到环境变量（如果存在）"""
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    key, val = key.strip(), val.strip()
                    if key not in os.environ:  # 不覆盖已有环境变量
                        os.environ[key] = val


_load_dotenv()


def load_config() -> dict:
    """加载 YAML 配置，替换环境变量占位符"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = f.read()

    # 替换 ${VAR} 环境变量
    import re
    def _env_replacer(match):
        var_name = match.group(1)
        return os.environ.get(var_name, "")
    raw = re.sub(r"\$\{(\w+)\}", _env_replacer, raw)

    return yaml.safe_load(raw)


def call_llm(prompt: str, config: dict, system_prompt: str = "") -> str:
    """调用 LLM（支持 DeepSeek / OpenAI / Anthropic / Gemini）"""
    provider = config["llm"]["provider"]
    api_key = config["llm"]["api_key"]
    base_url = config["llm"].get("base_url", "https://api.deepseek.com")
    model = config["llm"]["model"]
    temperature = config["llm"].get("temperature", 0.7)
    max_tokens = config["llm"].get("max_tokens", 8192)

    if not api_key:
        raise ValueError(f"API Key 未配置！请设置环境变量")

    if provider in ("deepseek", "openai"):
        # OpenAI 兼容接口
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    elif provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt if system_prompt else anthropic.NOT_GIVEN,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    elif provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model_obj = genai.GenerativeModel(model)
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        response = model_obj.generate_content(full_prompt)
        return response.text

    else:
        raise ValueError(f"不支持的 LLM provider: {provider}")


def parse_json_response(text: str) -> list[dict]:
    """从 LLM 返回文本中提取 JSON 数组"""
    # 去除 markdown 代码块
    text = text.strip()
    if text.startswith("```"):
        # 找到第一个换行后的内容
        lines = text.split("\n")
        text = "\n".join(lines[1:]) if len(lines) > 1 else text
        if text.endswith("```"):
            text = text[:-3]

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 JSON 数组
    import re
    match = re.search(r"\[\s*\{.*?\}\s*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 尝试逐行修复
    logger.error(f"无法解析 LLM 响应为 JSON:\n{text[:500]}")
    return []


def generate_ai_news(config: dict) -> list[dict]:
    """生成 AI 快讯板块"""
    from modules.ai_news import (
        fetch_rss_entries,
        fetch_github_trending,
        build_news_prompt,
        deduplicate_entries,
        DEFAULT_RSS_SOURCES,
    )
    news_config = config.get("ai_news", {})
    count = news_config.get("count", 10)

    logger.info("=" * 50)
    logger.info(f"📰 开始抓取 AI 新闻... (目标{count}条)")

    # 1. 抓取 RSS
    rss_sources = news_config.get("sources", {}).get("rss", DEFAULT_RSS_SOURCES)
    entries = fetch_rss_entries(rss_sources)

    # 2. 抓取 GitHub Trending
    if news_config.get("sources", {}).get("github_trending", True):
        gh_entries = fetch_github_trending()
        entries.extend(gh_entries)

    # 3. 去重
    entries = deduplicate_entries(entries)
    logger.info(f"📊 去重后: {len(entries)} 条候选新闻")

    if not entries:
        logger.error("没有抓取到任何新闻！")
        return []

    # 4. LLM 筛选 + 摘要
    prompt = build_news_prompt(entries, count)
    logger.info("🤖 调用 LLM 筛选 + 摘要...")
    response = call_llm(prompt, config, system_prompt="你是专业的AI科技新闻编辑，只返回JSON格式数据。")

    news_items = parse_json_response(response)
    logger.info(f"✅ AI快讯: {len(news_items)} 条")

    return news_items[:count]


def generate_ancient_stories(config: dict) -> list[dict]:
    """生成中国古代故事典故板块（带去重）"""
    stories_config = config.get("ancient_stories", {})
    count = stories_config.get("count", 10)
    categories = stories_config.get("categories", None)  # 从配置读取主题

    logger.info("=" * 50)
    logger.info(f"🏯 开始生成中国古代故事... (目标{count}则)")

    # ── 加载去重历史 ──
    history_titles = load_history(max_entries=300)
    if history_titles:
        logger.info(f"📋 去重库: {len(history_titles)} 条已推荐故事")

    # 展示统计
    stats = get_stats()
    if stats["total"] > 0:
        logger.info(f"📊 累计推荐: {stats['total']} 则 | 近7天: {stats['last_7_days']} 则")
        logger.info(f"📂 分类分布: {stats['categories']}")

    if categories:
        logger.info(f"🎯 配置主题({len(categories)}): {', '.join(categories)}")

    prompt = build_stories_prompt(count, history_titles, categories)
    logger.info("🤖 调用 LLM 生成故事...")
    response = call_llm(prompt, config, system_prompt="你是精通中国传统文化的历史学者，只返回JSON格式数据。")

    stories = parse_json_response(response)

    # ── 本地二次去重：万一 LLM 忽略了去重指令 ──
    if history_titles:
        history_set = set(history_titles)
        before = len(stories)
        stories = [s for s in stories if s.get("title", "") not in history_set]
        if len(stories) < before:
            logger.warning(f"⚠️ 去除了 {before - len(stories)} 条 LLM 重复推荐")

    logger.info(f"✅ 古代故事: {len(stories)} 则")

    # History is saved after email success (in main()), so failed retries
    # don't waste new stories on lost emails.
    return stories[:count]


def render_html(ai_news: list[dict], stories: list[dict]) -> str:
    """渲染 HTML 日报"""
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)

    template_path = TEMPLATE_DIR / "daily_report.html"
    with open(template_path, "r", encoding="utf-8") as f:
        template = Template(f.read())

    return template.render(
        date=now.strftime("%Y年%m月%d日"),
        ai_news=ai_news,
        stories=stories,
        generated_at=now.strftime("%Y-%m-%d %H:%M:%S 北京时间"),
    )


def generate_story_links(story: dict) -> list[tuple[str, str]]:
    """
    从故事关键词自动生成百度百科链接
    返回: [(显示文本, URL), ...]
    """
    links = []
    seen = set()

    def add_link(term: str):
        term = term.strip()
        if term and term not in seen and len(term) >= 2:
            seen.add(term)
            url = f"https://baike.baidu.com/item/{quote(term)}"
            links.append((term, url))

    # 1. LLM 生成的关键词（优先）
    for kw in story.get("keywords", []):
        add_link(kw)

    # 2. 从其他字段补充提取
    for char in story.get("characters", "").replace("、", "，").split("，"):
        add_link(char.strip())

    if story.get("title"):
        add_link(story.get("title", ""))

    # 提取出处文献名
    source = story.get("source", "")
    import re
    # 匹配《...》中的书名
    for book in re.findall(r"《(.+?)》", source):
        add_link(book)

    return links[:7]  # 最多7个链接，避免太多


def render_markdown(ai_news: list[dict], stories: list[dict]) -> str:
    """渲染 Markdown 日报（用于 GitHub Pages）"""
    today = datetime.now().strftime("%Y年%m月%d日")
    md = f"""# 📬 每日双拼日报 — {today}

> AI 快讯 · 洞察科技前沿 &nbsp;|&nbsp; 古代故事 · 品味千年智慧

---

## 🤖 AI 快讯 · 今日必读 ({len(ai_news)} 条精选)

"""
    for i, item in enumerate(ai_news, 1):
        stars = "★" * int(item.get("score", 3)) + "☆" * (5 - int(item.get("score", 3)))
        md += f"""### {i}. [{item['title']}]({item.get('url', '')}) {stars}

**来源**: {item.get('source', '')}

{item.get('summary_zh', '')}

"""

    md += f"""---

## 🏯 中国古代故事 · 典故 · 天文地理 · 科技发明 ({len(stories)} 则)

"""

    for i, story in enumerate(stories, 1):
        md += f"""### {i}. {story.get('title', '')}

**{story.get('dynasty', '')}** · {story.get('category', '')} · 出处：{story.get('source', '')}

{story.get('story_zh', '')}

"""
        if story.get("lesson"):
            md += f"> 💡 **寓意**：{story['lesson']}\n\n"
        if story.get("fun_fact"):
            md += f"> 📎 {story['fun_fact']}\n\n"

        # 百度百科链接
        links = story.get("_links", [])
        if links:
            md += "🔗 **深入了解**："
            md += " | ".join(f"[{text}]({url})" for text, url in links)
            md += "\n\n"

    md += f"""---

*📬 每日自动生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
    return md


def save_output(html_content: str, md_content: str, ai_news: list[dict], stories: list[dict]):
    """保存输出文件到 docs 目录"""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")

    # 保存 HTML
    html_path = DOCS_DIR / "index.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info(f"📄 HTML 日报: {html_path}")

    # 保存每日 Markdown
    md_path = DOCS_DIR / f"{today}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 同时保存 latest.md 方便引用
    latest_path = DOCS_DIR / "latest.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    logger.info(f"📝 Markdown 日报: {md_path}")

    # 保存 JSON 数据（方便后续搜索/分析）
    json_path = DOCS_DIR / f"{today}.json"
    json_data = {
        "date": today,
        "ai_news_count": len(ai_news),
        "stories_count": len(stories),
        "ai_news": [
            {
                "title": n.get("title", ""),
                "summary_zh": n.get("summary_zh", ""),
                "source": n.get("source", ""),
                "url": n.get("url", ""),
                "score": n.get("score", 3),
            }
            for n in ai_news
        ],
        "stories": [
            {
                "title": s.get("title", ""),
                "dynasty": s.get("dynasty", ""),
                "category": s.get("category", ""),
                "source": s.get("source", ""),
            }
            for s in stories
        ],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    logger.info(f"📊 JSON 数据: {json_path}")


def main():
    parser = argparse.ArgumentParser(description="每日双拼日报生成器")
    parser.add_argument("--news-only", action="store_true", help="仅生成AI快讯")
    parser.add_argument("--stories-only", action="store_true", help="仅生成古代故事")
    parser.add_argument("--no-email", action="store_true", help="跳过邮件发送")
    parser.add_argument("--stats", action="store_true", help="查看推荐统计")
    parser.add_argument("--recent", type=int, default=0, help="查看最近N条推荐标题")
    args = parser.parse_args()

    # ── 统计查询模式（不生成日报） ──
    if args.stats or args.recent > 0:
        stats = get_stats()
        print("\n📊 古代故事推荐统计")
        print("=" * 40)
        print(f"累计推荐: {stats['total']} 则")
        print(f"近7天推荐: {stats['last_7_days']} 则")
        print(f"\n📂 分类分布:")
        for cat, cnt in sorted(stats['categories'].items(), key=lambda x: -x[1]):
            bar = "█" * min(cnt, 30)
            print(f"  {cat:12s} {bar} {cnt}")
        print(f"\n📅 朝代分布:")
        for dyn, cnt in sorted(stats['dynasties'].items(), key=lambda x: -x[1]):
            print(f"  {dyn:8s} {cnt}")
        if args.recent > 0:
            print(f"\n📋 最近 {min(args.recent, len(stats['recent_titles']))} 条推荐:")
            for i, t in enumerate(stats['recent_titles'][-args.recent:], 1):
                print(f"  {i}. {t}")
        print()
        return

    logger.info("🚀 每日双拼日报 启动")
    logger.info(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 加载配置
    config = load_config()

    ai_news = []
    stories = []

    # ── 1. 生成 AI 快讯 ──
    if not args.stories_only and config.get("ai_news", {}).get("enabled", True):
        try:
            ai_news = generate_ai_news(config)
        except Exception as e:
            logger.error(f"AI快讯生成失败: {e}")
            traceback.print_exc()

    # ── 2. 生成古代故事 ──
    if not args.news_only and config.get("ancient_stories", {}).get("enabled", True):
        try:
            stories = generate_ancient_stories(config)
        except Exception as e:
            logger.error(f"古代故事生成失败: {e}")
            traceback.print_exc()

    # ── 3. 渲染输出 ──
    if not ai_news and not stories:
        logger.error("没有生成任何内容！请检查配置和 API Key。")
        sys.exit(1)

    logger.info("=" * 50)
    logger.info("🎨 渲染日报...")

    # 预计算百度百科链接
    for story in stories:
        story["_links"] = generate_story_links(story)

    html_content = render_html(ai_news, stories)
    md_content = render_markdown(ai_news, stories)

    # 保存文件
    save_output(html_content, md_content, ai_news, stories)

    # ── 4. 发送邮件 ──
    email_sent = args.no_email  # --no-email mode: skip sending, treat as "done"
    if not args.no_email and config.get("email", {}).get("enabled", False):
        logger.info("=" * 50)
        logger.info("📧 发送邮件...")
        email_config = config["email"]
        email_sent = send_daily_email(
            html_content=html_content,
            smtp_server=email_config["smtp_server"],
            smtp_port=email_config["smtp_port"],
            sender_email=email_config["sender_email"],
            sender_password=email_config["sender_password"],
            recipient_email=email_config["recipient_email"],
            subject=email_config.get("subject_template", "").replace("{date}", datetime.now().strftime("%Y-%m-%d")),
        )
        if not email_sent:
            logger.warning("邮件发送失败，日报已保存到 docs/，将在下次 cron 重试")

    # ── 只有邮件成功发送后才保存故事历史（去重库） ──
    #     这样如果邮件失败，下一轮 cron 重试时 LLM 还能生成同样的故事
    if stories and email_sent:
        save_to_history(stories)
    elif stories and not email_sent:
        logger.info("📋 邮件未成功，暂不更新去重库（等待重试）")

    # ── 5. 同步到 Notion ──
    notion_config = config.get("notion", {})
    if notion_config.get("enabled", False):
        logger.info("=" * 50)
        logger.info("📝 同步到 Notion...")
        from modules.notion_sync import create_daily_page
        notion_url = create_daily_page(
            token=notion_config.get("token", ""),
            page_id=notion_config.get("page_id", ""),
            ai_news=ai_news,
            stories=stories,
        )
        if notion_url:
            logger.info(f"📝 Notion 页面: {notion_url}")

    # ── 6. 生成小红书内容（暗黑编辑风卡片 + 爆款文案） ──
    xhs_config = config.get("xhs", {})
    if xhs_config.get("enabled", False) and ai_news:
        try:
            logger.info("=" * 50)
            logger.info("📱 生成小红书内容...")

            max_news = xhs_config.get("max_news", 10)

            # 6a. LLM 生成爆款文案
            from modules.xhs_content import build_xhs_prompt
            xhs_prompt = build_xhs_prompt(ai_news, max_news)
            logger.info("🤖 调用 LLM 生成小红书爆款文案...")
            xhs_response = call_llm(
                xhs_prompt, config,
                system_prompt="你是小红书AI科技赛道顶级博主，擅长创作爆款笔记。只返回JSON，不要markdown代码块。"
            )
            xhs_content = parse_json_response(xhs_response)
            if isinstance(xhs_content, dict) and xhs_content:
                logger.info(f"📝 XHS标题: {xhs_content.get('title', '')}")
                logger.info(f"🏷️ 标签: {', '.join(xhs_content.get('hashtags', []))}")
            else:
                logger.warning("LLM 未返回有效的小红书文案，使用默认内容")
                xhs_content = {
                    "title": f"📡 今日AI快讯 | {datetime.now().strftime('%m月%d日')}",
                    "body": "今日精选10条AI快讯已生成，详情见下方卡片 👇",
                    "hashtags": ["#AI", "#人工智能", "#AI快讯", "#科技前沿", "#每日AI"],
                    "headline_news": "今日AI快讯精选",
                }

            # 6b. LLM 为每条新闻生成「关键洞察 + 详细解读」
            from modules.xhs_content import build_enrich_prompt
            enrich_prompt = build_enrich_prompt(ai_news, max_news)
            logger.info("🤖 调用 LLM 为每条新闻补充洞察和详解...")
            enrich_response = call_llm(
                enrich_prompt, config,
                system_prompt="你是资深AI科技分析师。只返回JSON数组，不要markdown代码块。每条新闻补充一针见血的洞察和详细解读。"
            )
            enriched = parse_json_response(enrich_response)
            if isinstance(enriched, list) and enriched:
                # Merge enrichment into ai_news
                enrich_map = {e.get("index", -1): e for e in enriched if isinstance(e, dict)}
                for i, item in enumerate(ai_news[:max_news]):
                    idx = i + 1
                    if idx in enrich_map:
                        item["insight_zh"] = enrich_map[idx].get("insight_zh", "")
                        item["detail_zh"] = enrich_map[idx].get("detail_zh", "")
                logger.info(f"✅ 已为 {len(enrich_map)} 条新闻补充洞察/详解")
            else:
                logger.warning("LLM 未返回有效的补充内容，使用原始摘要")

            # 6c. 渲染图片卡片（HTML → Chrome → PNG）
            from modules.xhs_renderer import render_xhs_cards
            xhs_output_dir = xhs_config.get("output_dir", "docs/xhs")
            card_paths = render_xhs_cards(
                ai_news,
                output_dir=xhs_output_dir,
                max_news=max_news,
            )

            # 6c. 保存 XHS 发布清单
            xhs_manifest = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "title": xhs_content.get("title", ""),
                "body": xhs_content.get("body", ""),
                "hashtags": xhs_content.get("hashtags", []),
                "headline_news": xhs_content.get("headline_news", ""),
                "cards": card_paths,
            }
            manifest_path = DOCS_DIR / "xhs" / "manifest.json"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(xhs_manifest, f, ensure_ascii=False, indent=2)
            logger.info(f"📋 发布清单: {manifest_path}")
            logger.info(f"📱 小红书内容: {len(card_paths)} 张卡片 + 爆款文案")

        except Exception as e:
            logger.error(f"小红书内容生成失败: {e}")
            import traceback
            traceback.print_exc()

    logger.info("=" * 50)
    logger.info(f"✅ 完成！AI快讯 {len(ai_news)} 条 + 古代故事 {len(stories)} 则")
    logger.info(f"📂 输出目录: {DOCS_DIR}")


if __name__ == "__main__":
    main()
