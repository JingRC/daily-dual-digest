"""
Xiaohongshu content generator v2 — viral AI news copywriting

Creates XHS-optimized post text from daily AI news:
- Clickbait title (≤20 chars, curiosity-gap formula)
- Emoji-rich body text (scannable, high engagement)
- Algorithm-friendly hashtags
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def build_xhs_prompt(ai_news: list[dict], count: int = 10) -> str:
    """Build LLM prompt for XHS viral AI news post."""
    today = datetime.now().strftime("%Y年%m月%d日")

    # Summarize all AI news for the prompt
    news_blocks = []
    for i, item in enumerate(ai_news[:count], 1):
        score_stars = "★" * int(item.get("score", 3))
        news_blocks.append(
            f"#{i} [{score_stars}] {item.get('title', '')}\n"
            f"    来源: {item.get('source', '')}\n"
            f"    摘要: {item.get('summary_zh', '')[:200]}\n"
            f"    链接: {item.get('url', '')}"
        )
    news_str = "\n\n".join(news_blocks)

    prompt = f"""你是小红书 (Xiaohongshu / RED) AI科技赛道顶级博主，擅长创作爆款笔记。

今天是 {today}。以下是今日精选的 {len(ai_news[:count])} 条 AI 快讯，请为我创作一篇小红书笔记。

## 今日 AI 快讯素材

{news_str}

## 创作要求

### 1. 标题（≤20字，最重要！）
用「数字悬念 + 痛点/好奇心」公式，让人忍不住点击：
- "🚨 今天AI圈又地震了…"
- "刚刚！OpenAI深夜扔出核弹"
- "今天的AI快讯，第3条直接封神"
- "这10条AI新闻，条条炸裂"
- 1-2个emoji即可，不要堆砌

### 2. 正文（400-800字）
写作规范：
- **第一段**：用最炸裂的一条新闻开篇，制造紧迫感和好奇心
- 每条快讯用2-3句核心提炼，说重点不说废话
- 用 ⭐ 标注重要性（已给评分）
- 每段之间空一行，保持呼吸感
- 对每条快讯加一句「💬 锐评」——要有态度、有个性、敢下判断
- 末尾加互动：「你觉得哪条最有冲击力？评论区聊聊 👇」
- 禁止用 markdown 格式（不用 **、#、- 等），纯文字 + emoji
- 每条新闻结尾可以附上「原文：域名」格式的出处提示

### 3. 风格定位
- AI科技博主的人设：专业但不装逼、有观点、有审美
- 口语化但有深度，像懂技术的朋友在群里分享
- 信息密度高 + 阅读体验轻（看着不累）
- emoji 作为视觉锚点，但不要每条都加（控制在 1/3 的段落）

### 4. 话题标签（5-8个）
用小红书热门标签 + AI垂直标签：
#AI #人工智能 #AI快讯 #科技前沿 #每日AI #ChatGPT #OpenAI #大模型

## 返回格式

纯JSON，不要markdown代码块：

{{
  "title": "小红书标题（≤20字，带emoji）",
  "body": "小红书正文（400-800字，口语化，大量换行，emoji点缀）",
  "hashtags": ["#AI", "#人工智能", "#AI快讯", "#科技前沿", "#每日AI", "#ChatGPT", "#大模型"],
  "headline_news": "今日最炸裂的一条（5-10字文案，用于封面）"
}}"""

    return prompt


def build_enrich_prompt(ai_news: list[dict], count: int = 10) -> str:
    """Build prompt to enrich each news item with sharp insight + detailed body."""
    news_blocks = []
    for i, item in enumerate(ai_news[:count], 1):
        news_blocks.append(
            f"#{i} [{item.get('source','')}] {item.get('title','')}\n"
            f"    原摘要: {item.get('summary_zh','')[:150]}"
        )
    news_str = "\n\n".join(news_blocks)

    return f"""你是资深AI科技分析师，擅长一针见血的行业洞察。

对以下每条新闻，请补充两段内容：

## 1. 关键洞察 (insight_zh) — 30-50字
- 用一句话点出这条新闻的「为什么重要」「意味着什么」
- 要有观点、有态度、敢下判断
- 让读者产生"原来如此！"的感觉
- 举例："GPT-5 不仅是性能提升，更意味着 OpenAI 正在用降价策略收割开发者生态，这对 Anthropic 和 Google 是降维打击。"

## 2. 详细解读 (detail_zh) — 80-150字
- 更深入展开：背景、影响、与同类对比、后续展望
- 口语化但专业，像资深分析师在给朋友讲解
- 给出具体细节而非泛泛而谈
- 让读完的人比只看标题的人多知道一些东西

## 新闻列表
{news_str}

## 返回JSON数组（纯JSON，无markdown标记）
[
  {{
    "index": 1,
    "insight_zh": "一针见血的30-50字洞察",
    "detail_zh": "80-150字详细解读，背景+影响+展望"
  }},
  ...
]"""
