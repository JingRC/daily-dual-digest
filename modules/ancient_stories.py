"""
中国古代故事典故模块 —— LLM 每日精选生成10则（带去重）
"""
import hashlib
import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── 故事主题轮换池 ──────────────────────────────────────
STORY_CATEGORIES = [
    "成语典故",
    "历史故事",
    "诸子百家寓言",
    "唐诗宋词背后的故事",
    "古代名人逸事",
    "兵法谋略故事",
    "古代科技发明故事",
    "传统节日传说",
    "古代天文地理",
    "历史趣考",              # 有趣的历史考据/冷知识/推翻常识
]

# ── 历史记录路径 ───────────────────────────────────────
HISTORY_FILE = Path(__file__).parent.parent / "docs" / "story_history.json"


def load_history(max_entries: int = 300) -> list[str]:
    """
    加载已推荐过的故事标题列表（最近 N 条）
    返回标题列表，用于 LLM 去重
    """
    try:
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            titles = [entry["title"] for entry in data[-max_entries:]]
            logger.info(f"已加载历史记录: {len(titles)} 条已推荐故事")
            return titles
    except Exception as e:
        logger.warning(f"加载历史记录失败（将忽略去重）: {e}")
    return []


def save_to_history(stories: list[dict]) -> None:
    """
    将新生成的故事情节追加到历史记录
    仅保存标题 + 日期，不保存完整内容以节省空间
    """
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    today = datetime.now().strftime("%Y-%m-%d")
    for story in stories:
        existing.append({
            "date": today,
            "title": story.get("title", ""),
            "category": story.get("category", ""),
            "dynasty": story.get("dynasty", ""),
        })

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    logger.info(f"💾 历史记录已更新: {len(existing)} 条（新增 {len(stories)} 条）")


def get_daily_categories(categories: Optional[list[str]] = None) -> tuple[str, list[str]]:
    """
    基于日期 hash 确定当天的主题分布
    返回: (主主题, [辅助主题列表])
    """
    cats = categories if categories else STORY_CATEGORIES
    day_hash = int(hashlib.md5(datetime.now().strftime("%Y%m%d").encode()).hexdigest()[:8], 16)
    primary_cat = cats[day_hash % len(cats)]
    other_cats = [c for c in cats if c != primary_cat]
    random.seed(day_hash)
    secondary_cats = random.sample(other_cats, min(3, len(other_cats)))
    return primary_cat, secondary_cats


def build_stories_prompt(count: int = 10, history_titles: Optional[list[str]] = None, categories: Optional[list[str]] = None) -> str:
    """
    构建每日古代故事生成 prompt

    Args:
        count: 生成故事数量
        history_titles: 已推荐过的故事标题列表（用于去重）
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    primary_cat, secondary_cats = get_daily_categories(categories)

    # ── 去重清单 ──
    dedup_section = ""
    if history_titles and len(history_titles) > 0:
        dedup_section = f"""
## ⚠️ 去重要求（极其重要！）
以下 {len(history_titles)} 个故事**已经推荐过，今天绝对不能重复**：

{chr(10).join(f'- {t}' for t in history_titles[:200])}

请务必确保今天推荐的 {count} 个故事标题**不在此列表中**。如果列表太长记不住，至少确保不要命中最近推荐过的。
"""

    prompt = f"""你是一位精通中国传统文化的历史学者和故事讲述者。

今天是{today}。请为我**精选并创作{count}个中国古代故事典故**，要求：

## 主题分布
- 主要主题：**{primary_cat}**（占5-6则）
- 辅助主题：{', '.join(secondary_cats)}（各占1-2则）

## 质量要求
1. **准确性**：故事必须有可靠的古代文献出处（如《史记》《战国策》《世说新语》《资治通鉴》《左传》《汉书》《后汉书》《晋书》《唐书》《宋史》《明史》《山海经》《水经注》《徐霞客游记》《梦溪笔谈》《天工开物》等）
2. **多样性**：朝代覆盖先秦到明清，避免全部集中在三国/唐朝
3. **教育意义**：每个故事结尾点明寓意/教训/智慧
4. **文笔**：用现代通俗语言讲述，生动有趣，每则150-300字
5. **深度挖掘**：优先推荐知名度稍低但同样精彩的故事，不要总选守株待兔、亡羊补牢、画蛇添足这类小学课本成语
6. **主题适配**：
   - 古代天文地理类 → 推荐：二十八星宿传说、二十四节气由来、古代历法故事（如郭守敬编《授时历》）、古代地图绘制（如《禹贡地域图》）、地理大发现（如张骞通西域、郑和下西洋、徐霞客探长江源）、《山海经》中的地理神话、古代天象记录（如超新星观测）、都江堰/灵渠等古代水利工程
   - 历史趣考类 → 推荐：颠覆常识的历史冷知识（如司马光砸缸的缸在宋代能否烧制？曹冲称象的大象从哪来？草船借箭真实主角是孙权非诸葛亮？）、古代奇葩法律/制度、古代黑科技、被误读千年的历史细节（如焚书坑儒的真相）、考古发现推翻的认知。要有考据精神，引用具体文献/考古证据对比分析，不能只是段子
{dedup_section}

## 返回JSON数组（只返回JSON，不要markdown代码块）：
[
  {{
    "title": "故事标题（如：一鸣惊人、管鲍之交）",
    "category": "所属分类",
    "dynasty": "朝代（如：春秋/战国/西汉/唐/宋/明/清）",
    "source": "出处文献（如：《史记·滑稽列传》）",
    "characters": "主要人物",
    "story_zh": "150-300字的故事内容，通俗易懂",
    "lesson": "寓意/道理/智慧启示（30-50字）",
    "fun_fact": "一个相关的冷知识或趣闻（可选，30字以内）",
    "keywords": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"]
  }}
]

## keywords 字段说明
提供5个最相关的关键词（人物名、作品名、地名、事件名等），用于生成百度百科跳转链接。例如陆游的故事：["陆游", "钗头凤", "唐婉", "沈园", "宋词"]。词条名要准确，优先选百度百科中有独立词条的。

请确保故事内容准确、有趣、有教育意义。"""
    return prompt


def get_stats() -> dict:
    """获取推荐统计信息"""
    empty_stats = {"total": 0, "categories": {}, "dynasties": {}, "last_7_days": 0, "recent_titles": []}
    try:
        if not HISTORY_FILE.exists():
            return empty_stats

        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        from collections import Counter
        cats = Counter(entry.get("category", "未知") for entry in data)
        dynasties = Counter(entry.get("dynasty", "未知") for entry in data)

        from datetime import timedelta
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        recent = [e for e in data if e.get("date", "") >= week_ago]

        return {
            "total": len(data),
            "categories": dict(cats.most_common()),
            "dynasties": dict(dynasties.most_common()),
            "last_7_days": len(recent),
            "recent_titles": [e["title"] for e in data[-10:]],
        }
    except Exception:
        return empty_stats
