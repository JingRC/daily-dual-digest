"""
Xiaohongshu image card renderer v5 — Magazine editorial design

Every card structure:
  1. 图片区 — photo with page-number badge at TOP-RIGHT (frosted glass)
  2. 信息条 — source name + ★★★★★ star rating
  3. 标题 — bold headline
  4. 关键洞察 — sharp insight in accent-bordered box
  5. 详细解说 — detailed body text (400-600 chars)
  6. 页脚 — full article URL (with fallback) + page indicator

Output: {output_dir}/{YYYY-MM-DD}/{category}/
4 rotating layout styles vary typography/decoration, unified structure.
"""

import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

CARD_W = 1080
CARD_H = 1440

# ── Curated Unsplash photos ──
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

# ── Color palettes ──
PALETTES = [
    {"name": "verge",   "bg": "#0a0a0a", "accent": "#00ff88", "text": "#f0ece4", "muted": "#8a8578", "surface": "#1a1a18"},
    {"name": "wired",   "bg": "#0d0c0a", "accent": "#ff3366", "text": "#f2efe9", "muted": "#9a9488", "surface": "#1c1a16"},
    {"name": "indigo",  "bg": "#060d1a", "accent": "#4a9eff", "text": "#e8e4dd", "muted": "#7a8588", "surface": "#0f1628"},
    {"name": "noir",    "bg": "#111113", "accent": "#ff6b9d", "text": "#ede8e0", "muted": "#8a8278", "surface": "#1c1a1a"},
    {"name": "mint",    "bg": "#0a0f0c", "accent": "#00e5a0", "text": "#eef0ec", "muted": "#7a8078", "surface": "#141814"},
    {"name": "amber",   "bg": "#120e0b", "accent": "#ff8c42", "text": "#f0eae0", "muted": "#8a8075", "surface": "#1c1812"},
]

# ── Photo ratios (vary by layout for distinct text capacity) ──
# Editorial 34%: ~630 chars, Split 30%: ~700 chars, Swiss 35%: ~625 chars, Frame 32%: ~665 chars
PHOTO_RATIOS = [0.34, 0.30, 0.35, 0.32]


def _palette(index: int) -> dict:
    return PALETTES[index % len(PALETTES)]


def _photo(index: int) -> str:
    return UNSPLASH_BG[index % len(UNSPLASH_BG)]


def _build_shared_css(p: dict) -> str:
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
      body::after {{
        content: '';
        position: absolute; inset: 0; z-index: 999;
        pointer-events: none;
        background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.045'/%3E%3C/svg%3E");
        background-repeat: repeat;
      }}
      .photo-section {{
        position: absolute; top: 0; left: 0; right: 0;
        background: url('PHOTO_URL_PLACEHOLDER') center/cover no-repeat;
        z-index: 0;
      }}
      .photo-section::after {{
        content: '';
        position: absolute; inset: 0;
        background: linear-gradient(180deg,
          {p['bg']}00 55%,
          {p['bg']}ee 95%,
          {p['bg']} 100%);
      }}
      .content {{ position: relative; z-index: 2; height: 100%; display:flex; flex-direction:column; }}
      .page-badge {{
        position: absolute; z-index: 3;
        top: 32px; right: 60px;
        font-weight: 900; font-size: 130px;
        color: {p['accent']}99;
        text-shadow:
          0 0 30px {p['accent']}30,
          0 0 60px {p['accent']}18,
          0 2px 8px {p['bg']}40;
        -webkit-text-stroke: 1.5px {p['accent']}40;
        letter-spacing: -6px; line-height: 0.75;
      }}
      .meta {{ font-size: 24px; font-weight: 400; color: {p['accent']}; letter-spacing: 4px; text-transform: uppercase; }}
      .stars {{ font-size: 28px; color: {p['accent']}; letter-spacing: 4px; }}
      .title {{ font-weight: 900; line-height: 1.12; letter-spacing: -0.5px; }}
      .insight-box {{
        background: {p['surface']};
        border-left: 4px solid {p['accent']};
        border-radius: 0 8px 8px 0;
      }}
      .insight-label {{ font-size: 22px; font-weight: 700; color: {p['accent']}; letter-spacing: 3px; }}
      .insight-text {{ font-weight: 400; line-height: 1.55; }}
      .detail-text {{ font-weight: 300; line-height: 1.55; color: {p['muted']}; }}
      .source-tag {{ font-size: 22px; color: {p['muted']}; font-weight: 300; }}
      .brand {{ font-size: 18px; color: {p['muted']}; opacity: 0.5; letter-spacing: 3px; }}
      .hairline {{ width: 100%; height: 1px; background: {p['accent']}; opacity: 0.15; }}
      .accent-line {{ height: 3px; background: {p['accent']}; }}
      .folio {{ font-size: 20px; color: {p['muted']}; font-weight: 300; letter-spacing: 2px; }}
    </style>"""


def _extract_fields(item: dict) -> tuple:
    title = item.get("title", "")
    source = item.get("source", "")
    score = int(item.get("score", 3))
    stars = "★" * score + "☆" * (5 - score)
    summary = item.get("summary_zh", "")
    insight = item.get("insight_zh", "") or ""
    detail = item.get("detail_zh", "") or ""
    if not insight and summary:
        insight = summary[:80]
    if not detail:
        detail = summary[80:] if len(summary) > 80 else summary
    url = item.get("url", "")
    url_display = ""
    if url:
        from urllib.parse import urlparse
        try:
            pu = urlparse(url)
            if pu.netloc:
                url_display = pu.netloc + pu.path
                if url_display.endswith("/") and pu.path == "/":
                    url_display = pu.netloc
            if len(url_display) > 80:
                url_display = url_display[:77] + "..."
        except Exception:
            pass
    if not url_display:
        url_display = source if source else ""
    return title, source, score, stars, summary, insight, detail, url, url_display


# ═══════════════════════════════════════════════════════════════
# Layout 0 — Editorial: full-bleed photo + bold overlay typography
# ═══════════════════════════════════════════════════════════════

def _layout_editorial(item: dict, idx: int, total: int, pal_index: int) -> str:
    p = _palette(pal_index)
    photo = _photo(pal_index)
    css = _build_shared_css(p).replace("PHOTO_URL_PLACEHOLDER", photo)
    title, source, score, stars, summary, insight, detail, url, url_display = _extract_fields(item)
    photo_h = int(CARD_H * PHOTO_RATIOS[0])

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{css}</head><body>
<div class="photo-section" style="height:{photo_h}px;"></div>
<div class="page-badge">{idx:02d}</div>
<div class="content" style="padding:0 80px; padding-top:{photo_h + 24}px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
    <div class="meta">{source}</div>
    <div class="stars">{stars}</div>
  </div>
  <div class="title" style="font-size:48px;margin-bottom:22px;">{title}</div>
  <div class="insight-box" style="padding:20px 30px;margin-bottom:20px;">
    <div class="insight-label">⟡ 关键洞察</div>
    <div class="insight-text" style="margin-top:8px;font-size:26px;">{insight}</div>
  </div>
  <div class="detail-text" style="flex:1;font-size:25px;">{detail}</div>
  <div class="hairline" style="margin:14px 0 10px;"></div>
  <div style="display:flex;justify-content:space-between;align-items:center;padding-bottom:40px;">
    <div style="font-size:21px;color:{p['accent']};font-weight:400;">{'🔗 '+url_display if url_display else ''}</div>
    <div class="folio">{idx} / {total}</div>
  </div>
</div></body></html>"""


# ═══════════════════════════════════════════════════════════════
# Layout 1 — Split: max-text, smallest photo
# ═══════════════════════════════════════════════════════════════

def _layout_split(item: dict, idx: int, total: int, pal_index: int) -> str:
    p = _palette(pal_index)
    photo = _photo(pal_index)
    css = _build_shared_css(p).replace("PHOTO_URL_PLACEHOLDER", photo)
    title, source, score, stars, summary, insight, detail, url, url_display = _extract_fields(item)
    photo_h = int(CARD_H * PHOTO_RATIOS[1])

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{css}</head><body>
<div class="photo-section" style="height:{photo_h}px;"></div>
<div class="page-badge">{idx:02d}</div>
<div class="content" style="padding:0 72px; padding-top:{photo_h + 20}px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
    <div class="meta">{source}</div>
    <div class="stars">{stars}</div>
  </div>
  <div class="title" style="font-size:44px;margin-bottom:20px;">{title}</div>
  <div class="insight-box" style="padding:18px 28px;margin-bottom:18px;">
    <div class="insight-label">⟡ 关键洞察</div>
    <div class="insight-text" style="margin-top:6px;font-size:25px;">{insight}</div>
  </div>
  <div class="detail-text" style="flex:1;font-size:24px;">{detail}</div>
  <div class="hairline" style="margin:12px 0 8px;"></div>
  <div style="display:flex;justify-content:space-between;align-items:center;padding-bottom:38px;">
    <div style="font-size:20px;color:{p['accent']};font-weight:400;">{'🔗 '+url_display if url_display else ''}</div>
    <div class="folio">{idx} / {total}</div>
  </div>
</div></body></html>"""


# ═══════════════════════════════════════════════════════════════
# Layout 2 — Swiss: balanced, photo + bold number
# ═══════════════════════════════════════════════════════════════

def _layout_swiss(item: dict, idx: int, total: int, pal_index: int) -> str:
    p = _palette(pal_index)
    photo = _photo(pal_index)
    css = _build_shared_css(p).replace("PHOTO_URL_PLACEHOLDER", photo)
    title, source, score, stars, summary, insight, detail, url, url_display = _extract_fields(item)
    photo_h = int(CARD_H * PHOTO_RATIOS[2])

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{css}</head><body>
<div class="photo-section" style="height:{photo_h}px;"></div>
<div class="page-badge">{idx:02d}</div>
<div class="content" style="padding:0 76px; padding-top:{photo_h + 22}px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
    <div class="meta">{source}</div>
    <div class="stars">{stars}</div>
  </div>
  <div class="title" style="font-size:46px;margin-bottom:20px;">{title}</div>
  <div class="insight-box" style="padding:20px 30px;margin-bottom:20px;">
    <div class="insight-label">K E Y &nbsp; I N S I G H T</div>
    <div class="insight-text" style="margin-top:8px;font-size:25px;">{insight}</div>
  </div>
  <div class="detail-text" style="flex:1;font-size:25px;">{detail}</div>
  <div class="hairline" style="margin:12px 0 10px;"></div>
  <div style="display:flex;justify-content:space-between;align-items:center;padding-bottom:40px;">
    <div style="font-size:20px;color:{p['accent']};font-weight:400;">{'🔗 '+url_display if url_display else ''}</div>
    <div class="folio">{idx} / {total}</div>
  </div>
</div></body></html>"""


# ═══════════════════════════════════════════════════════════════
# Layout 3 — Frame: accent border, text-heavy
# ═══════════════════════════════════════════════════════════════

def _layout_frame(item: dict, idx: int, total: int, pal_index: int) -> str:
    p = _palette(pal_index)
    photo = _photo(pal_index)
    css = _build_shared_css(p).replace("PHOTO_URL_PLACEHOLDER", photo)
    title, source, score, stars, summary, insight, detail, url, url_display = _extract_fields(item)
    photo_h = int(CARD_H * PHOTO_RATIOS[3])

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{css}</head><body>
<div style="position:absolute;left:0;top:0;bottom:0;width:6px;background:{p['accent']};z-index:3;"></div>
<div class="photo-section" style="height:{photo_h}px;left:6px;right:0;">
  <div style="position:absolute;bottom:0;left:0;right:0;height:4px;background:{p['accent']};z-index:4;opacity:0.7;"></div>
</div>
<div class="page-badge">{idx:02d}</div>
<div class="content" style="padding:0 82px; padding-top:{photo_h + 24}px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
    <div class="meta">{source}</div>
    <div class="stars">{stars}</div>
  </div>
  <div class="title" style="font-size:46px;margin-bottom:20px;">{title}</div>
  <div class="insight-box" style="padding:18px 28px;margin-bottom:18px;">
    <div class="insight-label">⟡ 关键洞察</div>
    <div class="insight-text" style="margin-top:6px;font-size:25px;">{insight}</div>
  </div>
  <div class="detail-text" style="flex:1;font-size:25px;">{detail}</div>
  <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 0 38px;margin-top:12px;border-top:1px solid {p['accent']}20;">
    <div style="font-size:20px;color:{p['accent']};font-weight:400;">{'🔗 '+url_display if url_display else ''}</div>
    <div class="folio">{idx} / {total}</div>
  </div>
</div></body></html>"""


# ═══════════════════════════════════════════════════════════════
# Cover & Summary
# ═══════════════════════════════════════════════════════════════

def _build_cover_html(date_str: str, count: int, pal_index: int) -> str:
    p = _palette(pal_index)
    photo = _photo(pal_index)
    css = _build_shared_css(p).replace("PHOTO_URL_PLACEHOLDER", photo)
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{css}</head><body>
<div class="photo-section" style="height:100%;opacity:0.5;"></div>
<div class="content" style="align-items:center;justify-content:center;text-align:center;padding:100px 80px;">
  <div class="meta" style="margin-bottom:60px;">D A I L Y &nbsp; D I G E S T</div>
  <div style="font-size:120px;font-weight:900;color:{p['accent']};opacity:0.85;letter-spacing:-6px;line-height:1;margin-bottom:32px;">{count}</div>
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


def _build_summary_html(news: list[dict], date_str: str) -> str:
    p = _palette(0)
    css = _build_shared_css(p).replace("PHOTO_URL_PLACEHOLDER", "")
    items = ""
    for i, item in enumerate(news[:10], 1):
        s = "★" * int(item.get("score", 3))
        items += f"""<div style="display:flex;gap:20px;padding:18px 0;border-bottom:1px solid {p['accent']}12;align-items:center;">
  <div style="font-size:26px;font-weight:900;color:{p['accent']};min-width:36px;">{i:02d}</div>
  <div style="flex:1;"><div style="font-size:25px;font-weight:600;line-height:1.45;">{item.get('title','')}</div>
  <div style="font-size:20px;color:{p['muted']};margin-top:6px;">{item.get('source','')}</div></div>
  <div class="stars">{s}</div>
</div>"""
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{css}</head><body>
<div class="content" style="padding:80px 72px 60px;">
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


def _build_news_card_html(item: dict, idx: int, total: int) -> str:
    layout = idx % 4
    pal_index = idx % len(PALETTES)
    if layout == 0:
        return _layout_editorial(item, idx, total, pal_index)
    elif layout == 1:
        return _layout_split(item, idx, total, pal_index)
    elif layout == 2:
        return _layout_swiss(item, idx, total, pal_index)
    else:
        return _layout_frame(item, idx, total, pal_index)


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
                     max_news: int = 10,
                     category: str = "科技报") -> list[str]:
    """Render 1 cover + N news cards + 1 summary card.

    Output: {output_dir}/{YYYY-MM-DD}/{category}/
    """
    today_cn = datetime.now().strftime("%Y年%m月%d日")
    date_folder = datetime.now().strftime("%Y-%m-%d")
    out = Path(output_dir) / date_folder / category
    out.mkdir(parents=True, exist_ok=True)

    paths = []
    selected = ai_news[:max_news]
    total = 2 + len(selected)

    logger.info(f"[XHS] Rendering {total} cards -> {out}/ (v5: glass badge, 400-600char detail)")

    # 1. Cover
    html = _build_cover_html(today_cn, len(selected), 0)
    png = out / "01_cover.png"
    render_html_to_png(html, str(png))
    paths.append(str(png))
    logger.info(f"  [1/{total}] Cover -> {png.name}")

    # 2. News cards
    for i, item in enumerate(selected):
        n = i + 2
        html = _build_news_card_html(item, i + 1, len(selected))
        png = out / f"{n:02d}_news_{i+1:02d}.png"
        render_html_to_png(html, str(png))
        paths.append(str(png))
        layout_name = ["Editorial", "Split", "Swiss", "Frame"][i % 4]
        logger.info(f"  [{n}/{total}] {item.get('title','')[:36]}... [{layout_name}] -> {png.name}")

    # 3. Summary
    n = total
    html = _build_summary_html(selected, today_cn)
    png = out / f"{n:02d}_summary.png"
    render_html_to_png(html, str(png))
    paths.append(str(png))
    logger.info(f"  [{n}/{total}] Summary -> {png.name}")

    logger.info(f"[XHS] Done: {len(paths)} cards -> {out}/")
    return paths
