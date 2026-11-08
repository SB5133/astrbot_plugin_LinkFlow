# -*- coding: utf-8 -*-
"""浏览器方案卡片渲染

版式来自设计器导出的 core/resources/card_layout.json（与 card_designer.html 样式一致），
本模块按版式生成 HTML 并 POST 给宿主渲染服务（headless Chromium）截图返回 PNG。
任何一步失败都返回 None，由调用方回退 PIL 渲染。
"""
from __future__ import annotations

import base64
import html as html_mod
import io
import json
import re
from pathlib import Path
from typing import Any

import aiohttp
from PIL import Image

from astrbot.api import logger

RESOURCES_DIR = Path(__file__).parent / "resources"
LAYOUT_PATH = RESOURCES_DIR / "card_layout.json"
DEFAULT_WALLPAPER = RESOURCES_DIR / "card_bg_default.jpg"
DEFAULT_RENDER_URL = "http://127.0.0.1:8790/render"
RENDER_TIMEOUT = 60

# 平台胶囊样式: name -> (角标文字, 角标底色)
PLATFORM_STYLE: dict[str, tuple[str, str]] = {
    "bilibili": ("B", "#FB7299"),
    "kuaishou": ("快", "#FF4906"),
    "douyin": ("抖", "#000000"),
    "weibo": ("微", "#E6162D"),
    "xhs": ("书", "#FF2442"),
    "zhihu": ("知", "#0084FF"),
    "youtube": ("YT", "#FF0000"),
    "twitter": ("X", "#000000"),
    "ncm": ("云", "#C20C0C"),
}
_DEFAULT_STYLE = ("·", "#e05e8a")

# ---------------------------------------------------------------- 文本清洗

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_WS_RE = re.compile(r"\s+")
_DESC_PREFIX_RE = re.compile(r"^简介\s*[:：]\s*")


def clean_desc(text: str | None) -> str:
    """清简介：去「简介:」前缀、去裸链接、压缩空白"""
    if not text:
        return ""
    t = _DESC_PREFIX_RE.sub("", text.strip())
    t = _URL_RE.sub(" ", t)
    t = _WS_RE.sub(" ", t).strip()
    t = re.sub(r"^[\s|·—\-:：,，]+", "", t)
    t = re.sub(r"[\s|·—\-:：,，]+$", "", t)
    return t.strip()


def fmt_num(v: Any) -> str:
    """34274 -> 3.4万；字符串原样返回"""
    if isinstance(v, str):
        return v
    try:
        n = int(v)
    except (TypeError, ValueError):
        return str(v)
    if n >= 10000:
        s = ("%.1f" % (n / 10000)).rstrip("0").rstrip(".")
        return s + "万"
    return str(n)


# ---------------------------------------------------------------- HTML 生成

_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
html,body { width:__W__px; height:__H__px; overflow:hidden; }
#stage { position:relative; width:__W__px; height:__H__px;
  font-family:"Microsoft YaHei",system-ui,sans-serif; }
#stage img.bg { position:absolute; left:-2%; top:-2%; width:104%; height:104%;
  object-fit:cover; user-select:none; filter:blur(__BLUR__px); }
.glass { background:rgba(255,255,255,.42); backdrop-filter:blur(16px) saturate(1.35);
  -webkit-backdrop-filter:blur(16px) saturate(1.35);
  border:1.5px solid rgba(255,255,255,.75); box-shadow:0 6px 24px rgba(31,38,135,.22); }
#title_card { border-radius:14px; padding:12px 18px; }
#title { font-size:24px; font-weight:700; color:#1f2937; line-height:1.3;
  overflow-wrap:anywhere; }
#desc_card { border-radius:14px; padding:14px 18px; }
#desc { font-size:15px; color:#4b5563; line-height:1.55;
  overflow-wrap:anywhere; }
#stats_card { border-radius:14px; padding:12px 20px; }
#stats { display:flex; align-items:center; gap:26px; font-size:15px; color:#374151; font-weight:600; }
#stats .st { display:flex; align-items:center; gap:6px; white-space:nowrap; }
#platform { display:flex; align-items:center; gap:8px; background:rgba(255,255,255,.6);
  backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px);
  border-radius:999px; padding:6px 16px; border:1.5px solid rgba(255,255,255,.85);
  font-size:15px; color:#374151; font-weight:600; }
#platform .logo { width:22px; height:22px; border-radius:6px; background:__PLATCOLOR__;
  display:flex; align-items:center; justify-content:center; color:#fff;
  font-size:12px; font-weight:700; flex-shrink:0; }
#author { display:flex; align-items:center; gap:10px; background:rgba(255,255,255,.6);
  backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px);
  border-radius:999px; padding:5px 18px 5px 5px; border:1.5px solid rgba(255,255,255,.85); }
#author .avatar { width:38px; height:38px; border-radius:50%; object-fit:cover;
  background:linear-gradient(135deg,#f093fb,#f5576c); flex-shrink:0; border:2px solid #fff; }
#author .name { font-size:16px; font-weight:600; color:#1f2937;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
"""

_BODY = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><style>__CSS__</style></head>
<body><div id="stage">
  <img class="bg" src="__WALL__">
  <div id="platform"><span class="logo">__PLATABBR__</span><span class="ptext">__PLATNAME__</span></div>
  <div id="author"><img class="avatar" src="__AVATAR__" alt=""><span class="name">__AUTHOR__</span></div>
  <div class="glass" id="title_card"><div id="title">__TITLE__</div></div>
  <div class="glass" id="desc_card"><div id="desc">__DESC__</div></div>
  <div class="glass" id="stats_card"><div id="stats">__STATS__</div></div>
</div>
<script>
(function () {
  /* 标题/文案不截断: 卡片 width/height:auto 会先跟随内容扩大到 max 范围，
     仅在内容超出 max(最大范围)时二分缩小字号兜底，保证永不裁切 */
  function fitText(el, base, min, maxW, maxH) {
    if (!el) return;
    el.style.fontSize = base + "px";
    var fits = function () {
      return el.scrollWidth <= maxW + 1 && el.scrollHeight <= maxH + 1;
    };
    if (fits()) return;
    var lo = min, hi = base, best = min;
    while (lo <= hi) {
      var mid = (lo + hi) / 2;
      el.style.fontSize = mid + "px";
      if (fits()) { best = mid; lo = mid + 0.5; } else { hi = mid - 0.5; }
    }
    el.style.fontSize = best + "px";
  }
  var FIT = __FIT__;
  for (var i = 0; i < FIT.length; i++) {
    var f = FIT[i];
    fitText(document.getElementById(f.sel), f.base, f.min, f.maxW, f.maxH);
  }
})();
</script>
</body></html>
"""

_LAYOUT_CACHE: dict | None = None


def load_layout(path: Path | None = None) -> dict:
    """加载版式（带缓存）"""
    global _LAYOUT_CACHE
    if path is not None:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    if _LAYOUT_CACHE is None:
        _LAYOUT_CACHE = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    return _LAYOUT_CACHE


def _b64_local(path: Path, resize_w: int | None = None) -> str:
    """本地图片 -> JPEG base64 data URI（可先降宽度）"""
    with Image.open(path) as im:
        im = im.convert("RGB")
        if resize_w and im.width > resize_w:
            im = im.resize((resize_w, round(im.height * resize_w / im.width)),
                           Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


async def _b64_fetch(url: str, resize_w: int | None = None,
                     referer: str | None = None) -> str | None:
    """下载远程图片 -> base64 data URI；失败返回 None"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                             "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"}
    if referer:
        headers["Referer"] = referer
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
    except Exception as e:
        logger.debug(f"[BrowserRender] 图片下载失败 {url}: {e}")
        return None
    try:
        with Image.open(io.BytesIO(data)) as im:
            im = im.convert("RGB")
            if resize_w and im.width > resize_w:
                im = im.resize((resize_w, round(im.height * resize_w / im.width)),
                               Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=88, optimize=True)
    except Exception as e:
        logger.debug(f"[BrowserRender] 图片解码失败 {url}: {e}")
        return None
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def build_card_html(meta: dict, wallpaper: str, layout: dict) -> str:
    """按版式生成卡片 HTML

    meta: {platform:{name,abbr,color}, author, avatar, title, desc, stats}
    wallpaper: 壁纸 data URI
    layout: 设计器导出版式
    """
    W = int(layout.get("width", 1280))
    H = int(layout.get("height", 722))
    els = layout.get("elements", {})
    plat = meta.get("platform") or {}
    title = (meta.get("title") or "").strip()
    desc = clean_desc(meta.get("desc"))
    stats = meta.get("stats") or {}

    rules: list[str] = []
    fit: list[dict] = []
    # 文字板自适应参数: (选择器, 基础字号, 最小字号, 文本可用宽/高)
    # 可用高同时受版式 max_h 和"不超出画布"约束
    _FIT_SPEC = {
        "title_card": ("title", 24, 13, 24),   # padding 12px 上下
        "desc_card": ("desc", 15, 10, 28),     # padding 14px 上下
    }
    for name in ("title_card", "desc_card", "stats_card", "platform", "author"):
        L = els.get(name)
        if not L or not L.get("visible", True):
            continue
        if name == "title_card" and not title:
            continue
        if name == "desc_card" and not desc:
            continue
        if name == "stats_card" and not stats:
            continue
        align = L.get("align") or "left"
        justify = {"center": "center", "right": "flex-end"}.get(align, "flex-start")
        rules.append(
            "#%s { position:absolute;left:%dpx;top:%dpx;width:auto;height:auto;"
            "max-width:%dpx;max-height:%dpx;display:%s;justify-content:%s;text-align:%s; }"
            % (name, int(L["x"]), int(L["y"]), int(L["max_w"]), int(L["max_h"]),
               "flex" if name in ("platform", "author") else "block",
               justify, align)
        )
        if name in _FIT_SPEC:
            sel, base, min_size, pad_v = _FIT_SPEC[name]
            avail_h = min(int(L["max_h"]) - pad_v, H - int(L["y"]) - 8)
            fit.append({"sel": sel, "base": base, "min": min_size,
                        "maxW": int(L["max_w"]) - 36,
                        "maxH": max(40, avail_h)})

    stats_html = ""
    if stats:
        parts = []
        for key, label in (("play", "播放"), ("like", "点赞"),
                           ("fav", "收藏"), ("share", "转发")):
            if key in stats:
                parts.append('<span class="st">%s %s</span>'
                             % (label, html_mod.escape(fmt_num(stats[key]))))
        stats_html = "".join(parts)

    css = (_CSS.replace("__W__", str(W)).replace("__H__", str(H))
              .replace("__BLUR__", str(layout.get("bg_blur", 3)))
              .replace("__PLATCOLOR__", plat.get("color", _DEFAULT_STYLE[1])))
    css += "\n" + "\n".join(rules) + "\n"

    fit_json = "[" + ", ".join(
        '{sel:"%s",base:%d,min:%d,maxW:%d,maxH:%d}' % (
            f["sel"], f["base"], f["min"], f["maxW"], f["maxH"])
        for f in fit) + "]"

    return (_BODY.replace("__CSS__", css)
                  .replace("__FIT__", fit_json)
                  .replace("__WALL__", wallpaper)
                  .replace("__AVATAR__", meta.get("avatar") or "")
                  .replace("__AUTHOR__", html_mod.escape(meta.get("author") or ""))
                  .replace("__PLATABBR__", html_mod.escape(plat.get("abbr") or ""))
                  .replace("__PLATNAME__", html_mod.escape(plat.get("name") or ""))
                  .replace("__TITLE__", html_mod.escape(title))
                  .replace("__DESC__", html_mod.escape(desc))
                  .replace("__STATS__", stats_html))


async def card_meta_from_result(result: Any) -> dict:
    """ParseResult -> 卡片 meta"""
    plat_name = (getattr(result.platform, "name", "") or "").lower()
    abbr, color = PLATFORM_STYLE.get(plat_name, _DEFAULT_STYLE)
    display = getattr(result.platform, "display_name", None) or plat_name or "未知平台"

    author_name = ""
    avatar = ""
    if result.author is not None:
        author_name = result.author.name or ""
        try:
            avatar_path = await result.author.get_avatar_path()
        except Exception:
            avatar_path = None
        if avatar_path and Path(avatar_path).is_file():
            avatar = _b64_local(Path(avatar_path), 96)

    extra = result.extra or {}
    stats = {}
    for key, src in (("play", "view"), ("like", "like"),
                     ("fav", "favorite"), ("share", "share")):
        v = extra.get(src)
        if v is not None and str(v) != "":
            stats[key] = v

    return {
        "platform": {"name": display, "abbr": abbr, "color": color},
        "author": author_name,
        "avatar": avatar,
        "title": result.title or "",
        "desc": result.text or "",
        "stats": stats,
    }


def _resolve_wallpaper(cfg: Any) -> Path | None:
    """壁纸优先级: 配置 card_bg_image > 内置默认壁纸"""
    raw = (getattr(cfg, "card_bg_image", "") or "").strip()
    if raw:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = Path(cfg.data_dir) / path
        if path.is_file():
            return path
        logger.warning(f"[BrowserRender] 配置的背景图不存在: {path}，使用内置默认壁纸")
    return DEFAULT_WALLPAPER if DEFAULT_WALLPAPER.is_file() else None


async def render_browser_card(result: Any, cfg: Any, out_path: Path) -> Path | None:
    """浏览器方案渲染卡片；失败返回 None（调用方回退 PIL）

    Args:
        result: ParseResult
        cfg: 插件配置（card_render_url / card_bg_image / data_dir）
        out_path: 输出 PNG 路径
    """
    if result.repost is not None:
        return None  # 转发嵌套内容版式未覆盖，走 PIL
    meta = await card_meta_from_result(result)
    if not meta["title"] and not meta["desc"]:
        return None  # 无文字内容，交给 PIL（它会走纯文本降级）

    wallpaper_path = _resolve_wallpaper(cfg)
    if wallpaper_path is None:
        logger.warning("[BrowserRender] 无可用壁纸，回退 PIL")
        return None
    wallpaper = _b64_local(wallpaper_path, int(load_layout().get("width", 1280)))

    html = build_card_html(meta, wallpaper, load_layout())
    url = getattr(cfg, "card_render_url", None) or DEFAULT_RENDER_URL
    payload = {"html": html,
               "width": int(load_layout().get("width", 1280)),
               "height": int(load_layout().get("height", 722))}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload,
                timeout=aiohttp.ClientTimeout(total=RENDER_TIMEOUT),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"[BrowserRender] 渲染服务返回 {resp.status}，回退 PIL")
                    return None
                data = await resp.read()
    except Exception as e:
        logger.warning(f"[BrowserRender] 渲染服务不可用({url}): {e}，回退 PIL")
        return None

    if not data or data[:8] != b"\x89PNG\r\n\x1a\n":
        logger.warning("[BrowserRender] 渲染服务返回了非 PNG 数据，回退 PIL")
        return None
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
    except Exception as e:
        logger.error(f"[BrowserRender] 卡片落盘失败: {e}")
        return None
    return out_path
