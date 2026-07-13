"""
Xiaohongshu image card renderer v3 — Premium Editorial / Magazine Style

Design philosophy (anti-AI aesthetic):
- Real photography backgrounds (Unsplash) — NOT AI-generated pixels
- Asymmetric magazine layouts — NOT centered templates
- Curated color palettes — NOT algorithm-recommended gradients
- Paper texture + grain — NOT smooth plastic surfaces
- Bold bleed typography — NOT safe centered text

Renders via headless Chrome: HTML+CSS → 1080×1440 PNG (2x retina)
"""

import logging
import os
import random
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

CARD_W = 1080
CARD_H = 1440

# ── Curated Unsplash photos (tech/abstract, real photography) ──
UNSPLASH_BG = [
    "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=2160&q=80",
    "https://images.unsplash.com/photo-1518770660439-4636190af475?w=2160&q=80",
    "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=2160&q=80",
    "https://images.unsplash.com/photo-1535223289827-42f1e9919769?w=2160&q=80",
    "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=2160&q=80",
    "https://images.unsplash.com/photo-1558591710-4b4a1ae0f04d?w=2160&q=80",
    "https://images.unsplash.com/photo-1639322537228-f740dce8b2c3?w=2160&q=80",
    "https://images.unsplash.com/photo-1620641788421-7a1c342ea42e?w=2160&q=80",
]

# ── Curated color palettes (cycling, not random) ──
PALETTES = [
    {"name": "verge",   "bg": "#0a0a0a", "accent": "#00ff88", "text": "#f0ece4", "muted": "#8a8578", "surface": "#1a1a18"},
    {"name": "wired",   "bg": "#0d0c0a", "accent": "#ff3366", "text": "#f2efe9", "muted": "#9a9488", "surface": "#1c1a16"},
    {"name": "indigo",  "bg": "#060d1a", "accent": "#4a9eff", "text": "#e8e4dd", "muted": "#7a8588", "surface": "#0f1628"},
    {"name": "noir",    "bg": "#111113", "accent": "#ff6b9d", "text": "#ede8e0", "muted": "#8a8278", "surface": "#1c1a1a"},
    {"name": "mint",    "bg": "#0a0f0c", "accent": "#00e5a0", "text": "#eef0ec", "muted": "#7a8078", "surface": "#141814"},
    {"name": "amber",   "bg": "#120e0b", "accent": "#ff8c42", "text": "#f0eae0", "muted": "#8a8075", "surface": "#1c1812"},
]

# ── Layout templates (4 styles, rotate by index) ──
# 0: Editorial — full photo bg + bold text overlay
# 1: Split — photo top + text grid bottom
# 2: Swiss — no photo, pure typography + texture
# 3: Accent — accent block frame + centered text


def _palette(index: int) -> dict:
    return PALETTES[index % len(PALETTES)]


def _photo(index: int) -> str:
    return UNSPLASH_BG[index % len(UNSPLASH_BG)]


def _build_css(p: dict, layout: int, has_photo: bool, photo_idx: int = 0) -> str:
    """Build the CSS block for a card."""
    return f"""
    <style>
      * {{ margin:0; padding:0; box-sizing:border-box; }}
      body {{
        width: {CARD_W}px; height: {CARD_H}px;
        background: {p['bg']};
        font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
        color: {p['text']};
        overflow: hidden;
        position: relative;
      }}
      /* Paper grain overlay */
      body::after {{
        content: '';
        position: absolute; inset: 0; z-index: 999;
        pointer-events: none;
        background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.045'/%3E%3C/svg%3E");
        background-repeat: repeat;
      }}
      /* Photo background */
      .photo-bg {{
        position: absolute; inset: 0; z-index: 0;
        background: url('{_photo(photo_idx) if has_photo else ""}') center/cover no-repeat;
        opacity: {0.55 if has_photo else 0};
      }}
      .photo-bg::after {{
        content: '';
        position: absolute; inset: 0;
        background: linear-gradient(180deg, {p['bg']}00 30%, {p['bg']}cc 100%);
      }}
      .content {{ position: relative; z-index: 2; height: 100%; }}
      .meta {{ font-size: 24px; font-weight: 400; color: {p['accent']}; letter-spacing: 4px; text-transform: uppercase; }}
      .number {{ font-size: 180px; font-weight: 900; line-height: 0.75; color: {p['accent']}; opacity: 0.85; letter-spacing: -8px; }}
      .title {{ font-size: {52 if layout in (0,3) else 46}px; font-weight: 900; line-height: 1.1; letter-spacing: -0.5px; }}
      .summary {{ font-size: 28px; font-weight: 300; line-height: 1.65; color: {p['muted']}; }}
      .accent-line {{ width: 60px; height: 3px; background: {p['accent']}; }}
      .insight-box {{
        background: {p['surface']};
        border-left: 3px solid {p['accent']};
        padding: 28px 36px;
        border-radius: 0 8px 8px 0;
      }}
      .insight-label {{ font-size: 22px; font-weight: 700; color: {p['accent']}; letter-spacing: 3px; }}
      .insight-text {{ font-size: 26px; font-weight: 400; line-height: 1.55; }}
      .source-tag {{ font-size: 22px; color: {p['muted']}; font-weight: 300; }}
      .stars {{ font-size: 28px; color: {p['accent']}; letter-spacing: 4px; }}
      .brand {{ font-size: 18px; color: {p['muted']}; opacity: 0.5; letter-spacing: 3px; }}
      .hairline {{ width: 100%; height: 1px; background: {p['accent']}; opacity: 0.15; }}
    </style>"""


def _build_cover_html(date_str: str, count: int, pal_index: int) -> str:
    p = _palette(pal_index)
    css = _build_css(p, 0, True, pal_index)
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{css}</head><body>
<div class="photo-bg"></div><div class="content" style="display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:100px 80px;">
  <div class="meta" style="margin-bottom:60px;">D A I L Y &nbsp; D I G E S T</div>
  <div class="number" style="font-size:120px;line-height:1;margin-bottom:32px;">{count}</div>
  <div class="title" style="font-size:56px;margin-bottom:20px;">今日 AI 快讯精选</div>
  <div class="source-tag" style="font-size:28px;">{date_str}</div>
  <div class="accent-line" style="margin-top:48px;width:120px;"></div>
  <div style="display:flex;gap:60px;margin-top:56px;">
    <div style="text-align:center;"><div style="font-size:40px;font-weight:900;color:{p['accent']};">10</div><div class="source-tag" style="font-size:22px;">数据源</div></div>
    <div style="text-align:center;"><div style="font-size:40px;font-weight:900;color:{p['accent']};">{count}</div><div class="source-tag" style="font-size:22px;">条精选</div></div>
    <div style="text-align:center;"><div style="font-size:40px;font-weight:900;color:{p['accent']};">✦✦✦✦✦</div><div class="source-tag" style="font-size:22px;">LLM 评分</div></div>
  </div>
  <div class="brand" style="margin-top:80px;">每日双拼日报</div>
</div></body></html>"""


def _layout_editorial(item: dict, idx: int, total: int, pal_index: int) -> str:
    """Full photo bg, bold overlay — magazine cover feel."""
    p = _palette(pal_index)
    css = _build_css(p, 0, True, pal_index)
    title = item.get("title", "")
    source = item.get("source", "")
    score = int(item.get("score", 3))
    stars = "★" * score + "☆" * (5 - score)
    summary = item.get("summary_zh", "")
    url = item.get("url", "")
    domain = ""
    if url:
        from urllib.parse import urlparse
        try: domain = urlparse(url).netloc
        except: pass

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{css}</head><body>
<div class="photo-bg"></div><div class="content" style="display:flex;flex-direction:column;justify-content:flex-end;padding:72px 80px;">
  <div class="meta" style="margin-bottom:24px;">{source} &nbsp;·&nbsp; {stars}</div>
  <div class="title" style="font-size:58px;margin-bottom:36px;">{title}</div>
  <div class="summary" style="margin-bottom:40px;">{summary[:300]}</div>
  <div class="hairline" style="margin-bottom:32px;"></div>
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div class="source-tag">原文 {domain}</div>
    <div class="brand">每日双拼日报 · {idx}/{total}</div>
  </div>
</div></body></html>"""


def _layout_split(item: dict, idx: int, total: int, pal_index: int) -> str:
    """Photo in top half, text grid below."""
    p = _palette(pal_index)
    css = _build_css(p, 1, True, pal_index)
    title = item.get("title", "")
    source = item.get("source", "")
    score = int(item.get("score", 3))
    stars = "★" * score + "☆" * (5 - score)
    summary = item.get("summary_zh", "")
    insight = item.get("insight_zh", summary)[:140]
    url = item.get("url", "")
    from urllib.parse import urlparse
    domain = ""
    if url:
        try: domain = urlparse(url).netloc
        except: pass

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{css}</head><body>
<div class="photo-bg" style="height:45%;position:absolute;top:0;left:0;right:0;opacity:0.7;"></div>
<div class="content" style="display:flex;flex-direction:column;padding:0 72px;padding-top:48%;height:100%;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:28px;">
    <div class="meta">{source}</div>
    <div class="stars">{stars}</div>
  </div>
  <div class="title">{title}</div>
  <div class="accent-line" style="margin:32px 0;"></div>
  <div class="summary" style="flex:1;">{summary[:350]}</div>
  <div class="insight-box" style="margin:28px 0;">
    <div class="insight-label">⟡ 关键洞察</div>
    <div class="insight-text" style="margin-top:8px;">{insight}</div>
  </div>
  <div class="hairline"></div>
  <div style="display:flex;justify-content:space-between;padding:24px 0 60px;">
    <div class="source-tag">{'原文 '+domain if domain else ''}</div>
    <div class="brand">每日双拼日报 · {idx}/{total}</div>
  </div>
</div></body></html>"""


def _layout_swiss(item: dict, idx: int, total: int, pal_index: int) -> str:
    """Pure typography, no photo — Swiss International Style."""
    p = _palette(pal_index)
    css = _build_css(p, 2, False)
    title = item.get("title", "")
    source = item.get("source", "")
    score = int(item.get("score", 3))
    stars = "★" * score + "☆" * (5 - score)
    summary = item.get("summary_zh", "")
    url = item.get("url", "")
    from urllib.parse import urlparse
    domain = ""
    if url:
        try: domain = urlparse(url).netloc
        except: pass

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{css}</head><body>
<div class="content" style="display:flex;flex-direction:column;height:100%;padding:80px 80px 60px;">
  <div style="display:flex;gap:32px;align-items:flex-start;margin-bottom:48px;">
    <div class="number">{idx:02d}</div>
    <div style="flex:1;padding-top:20px;">
      <div style="display:flex;justify-content:space-between;">
        <div class="meta">{source}</div>
        <div class="stars">{stars}</div>
      </div>
    </div>
  </div>
  <div class="title" style="font-size:56px;margin-bottom:40px;">{title}</div>
  <div class="hairline" style="margin-bottom:40px;"></div>
  <div class="summary" style="flex:1;font-size:30px;">{summary[:380]}</div>
  <div class="insight-box">
    <div class="insight-label">K E Y &nbsp; T A K E A W A Y</div>
    <div class="insight-text" style="margin-top:10px;">{summary[:130]}</div>
  </div>
  <div style="display:flex;justify-content:space-between;margin-top:40px;">
    <div class="source-tag">{'原文 '+domain if domain else ''}</div>
    <div class="brand">每日双拼日报 · {idx}/{total}</div>
  </div>
</div></body></html>"""


def _layout_accent(item: dict, idx: int, total: int, pal_index: int) -> str:
    """Accent color frame + dramatic typography."""
    p = _palette(pal_index)
    css = _build_css(p, 3, False)
    title = item.get("title", "")
    source = item.get("source", "")
    score = int(item.get("score", 3))
    stars = "★" * score + "☆" * (5 - score)
    summary = item.get("summary_zh", "")
    url = item.get("url", "")
    from urllib.parse import urlparse
    domain = ""
    if url:
        try: domain = urlparse(url).netloc
        except: pass

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{css}</head><body>
<div style="position:absolute;left:0;top:0;bottom:0;width:8px;background:{p['accent']};z-index:3;"></div>
<div style="position:absolute;left:8px;top:0;right:0;bottom:0;border:1px solid {p['accent']}22;z-index:1;"></div>
<div class="content" style="display:flex;flex-direction:column;height:100%;padding:90px 90px 60px;position:relative;z-index:2;">
  <div class="meta" style="margin-bottom:16px;">{source} &nbsp;·&nbsp; {stars}</div>
  <div class="number" style="font-size:160px;margin-bottom:20px;">{idx:02d}</div>
  <div class="title" style="font-size:54px;margin-bottom:40px;">{title}</div>
  <div class="accent-line" style="width:80px;margin-bottom:36px;"></div>
  <div class="summary" style="flex:1;font-size:29px;">{summary[:350]}</div>
  <div style="display:flex;justify-content:space-between;padding-top:30px;border-top:1px solid {p['accent']}20;">
    <div class="source-tag">{'原文 '+domain if domain else ''}</div>
    <div class="brand">每日双拼日报 · {idx}/{total}</div>
  </div>
</div></body></html>"""


def _build_news_card_html(item: dict, idx: int, total: int) -> str:
    """Route to the appropriate layout template based on index."""
    layout = idx % 4  # Rotate through 4 layouts
    pal_index = idx % len(PALETTES)

    if layout == 0:
        return _layout_editorial(item, idx, total, pal_index)
    elif layout == 1:
        return _layout_split(item, idx, total, pal_index)
    elif layout == 2:
        return _layout_swiss(item, idx, total, pal_index)
    else:
        return _layout_accent(item, idx, total, pal_index)


def _build_summary_html(news: list[dict], date_str: str) -> str:
    """Final overview card."""
    p = _palette(0)
    css = _build_css(p, 2, False)
    items = ""
    for i, item in enumerate(news[:10], 1):
        s = "★" * int(item.get("score", 3))
        items += f"""<div style="display:flex;gap:20px;padding:18px 0;border-bottom:1px solid {p['accent']}12;align-items:flex-start;">
  <div style="font-size:26px;font-weight:900;color:{p['accent']};min-width:36px;">{i:02d}</div>
  <div style="flex:1;"><div style="font-size:25px;font-weight:600;line-height:1.45;">{item.get('title','')}</div>
  <div style="font-size:20px;color:{p['muted']};margin-top:8px;">{item.get('source','')} &nbsp; {s}</div></div>
</div>"""

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{css}</head><body>
<div class="content" style="display:flex;flex-direction:column;height:100%;padding:80px 72px 60px;">
  <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:32px;">
    <div class="title" style="font-size:44px;">今日快讯一览</div>
    <div class="source-tag">{date_str}</div>
  </div>
  <div class="hairline" style="margin-bottom:16px;"></div>
  <div style="flex:1;overflow:hidden;">{items}</div>
  <div class="hairline" style="margin-top:16px;"></div>
  <div style="display:flex;justify-content:space-between;padding-top:20px;">
    <div class="source-tag">HuggingFace · TechCrunch · The Verge · 36Kr · GitHub · arXiv</div>
    <div class="brand">每日双拼日报</div>
  </div>
</div></body></html>"""


# ── Chrome finder ─────────────────────────────────────────

def _find_chrome() -> str:
    env_chrome = os.environ.get("GOOGLE_CHROME_BIN", "")
    if env_chrome and os.path.exists(env_chrome):
        return env_chrome
    candidates = [
        "google-chrome", "google-chrome-stable", "chromium-browser", "chromium",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for c in candidates:
        if shutil.which(c) or os.path.exists(c):
            return c
    return "google-chrome"


# ── HTML → PNG ────────────────────────────────────────────

def render_html_to_png(html: str, png_path: str,
                       width: int = CARD_W, height: int = CARD_H) -> str:
    html_path = Path(png_path).with_suffix(".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    chrome = _find_chrome()
    abs_html = html_path.resolve().as_uri()
    abs_png = Path(png_path).resolve()

    cmd = [
        chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--disable-setuid-sandbox",
        f"--window-size={width},{height}",
        "--force-device-scale-factor=2",
        f"--screenshot={abs_png}",
        abs_html,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=30,
                   env={**os.environ, "DISPLAY": ":99"})
    try:
        os.remove(html_path)
    except OSError:
        pass
    if not os.path.exists(str(abs_png)) or os.path.getsize(str(abs_png)) < 100:
        raise RuntimeError(f"Chrome did not produce output at {abs_png}")
    return str(abs_png)


# ── Public API ────────────────────────────────────────────

def render_xhs_cards(ai_news: list[dict],
                     output_dir: str = "docs/xhs",
                     max_news: int = 10) -> list[str]:
    """Render 1 cover + N news cards + 1 summary card."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    today_cn = datetime.now().strftime("%Y年%m月%d日")
    date_file = datetime.now().strftime("%Y%m%d")
    paths = []
    selected = ai_news[:max_news]
    total = 2 + len(selected)

    logger.info(f"[XHS] Rendering {total} cards (Premium Editorial, 4 layouts, {len(PALETTES)} palettes)")

    # 1. Cover
    html = _build_cover_html(today_cn, len(selected), 0)
    png = out / f"{date_file}_01_cover.png"
    render_html_to_png(html, str(png))
    paths.append(str(png))
    logger.info(f"  [1/{total}] Cover -> {png.name}")

    # 2. News cards (rotating layouts + palettes)
    for i, item in enumerate(selected):
        n = i + 2
        html = _build_news_card_html(item, i + 1, len(selected))
        png = out / f"{date_file}_{n:02d}_news_{i+1:02d}.png"
        render_html_to_png(html, str(png))
        paths.append(str(png))
        layout_name = ["Editorial", "Split", "Swiss", "Accent"][i % 4]
        palette_name = PALETTES[i % len(PALETTES)]["name"]
        logger.info(f"  [{n}/{total}] {item.get('title','')[:36]}... [{layout_name}] [{palette_name}] -> {png.name}")

    # 3. Summary
    n = total
    html = _build_summary_html(selected, today_cn)
    png = out / f"{date_file}_{n:02d}_summary.png"
    render_html_to_png(html, str(png))
    paths.append(str(png))
    logger.info(f"  [{n}/{total}] Summary -> {png.name}")

    logger.info(f"[XHS] Done: {len(paths)} cards -> {out}/")
    return paths
