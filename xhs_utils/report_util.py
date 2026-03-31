import json
from copy import deepcopy
from datetime import datetime
from html import escape
from pathlib import Path

import requests


CONNECT_TIMEOUT = 10
READ_TIMEOUT = 120


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def write_task_bundle(task_meta, notes, output_dir, save_mode="all"):
    output_root = Path(output_dir)
    ensure_dir(output_root)
    use_local_media = save_mode in {"media", "all"}
    media_root = output_root / "media"
    if use_local_media:
        ensure_dir(media_root)

    prepared_notes = []
    for note in notes:
        prepared_notes.append(_prepare_note(note, output_root, media_root if use_local_media else None))

    payload = {
        "task": task_meta,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "note_count": len(prepared_notes),
        "notes": prepared_notes,
    }
    (output_root / "data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_root / "report.html").write_text(
        render_report_html(task_meta, prepared_notes),
        encoding="utf-8",
    )
    return output_root


def _prepare_note(note, output_root, media_root=None):
    prepared = deepcopy(note)
    prepared.setdefault("report_assets", {})
    prepared.setdefault("download_errors", [])

    if prepared.get("note_type") == "图集":
        prepared["report_assets"]["images"] = _prepare_images(
            prepared,
            output_root,
            media_root,
        )
    else:
        prepared["report_assets"]["cover"] = _prepare_single_asset(
            prepared.get("video_cover"),
            output_root,
            media_root,
            prepared["note_id"],
            "cover.jpg",
            prepared["download_errors"],
        )
        prepared["report_assets"]["video"] = _prepare_single_asset(
            prepared.get("video_addr"),
            output_root,
            media_root,
            prepared["note_id"],
            "video.mp4",
            prepared["download_errors"],
        )
    return prepared


def _prepare_images(note, output_root, media_root=None):
    report_images = []
    for index, image_url in enumerate(note.get("image_list", [])):
        report_images.append(
            _prepare_single_asset(
                image_url,
                output_root,
                media_root,
                note["note_id"],
                f"image_{index}.jpg",
                note["download_errors"],
            )
        )
    return report_images


def _prepare_single_asset(url, output_root, media_root, note_id, filename, download_errors):
    if not url:
        return None
    if media_root is None:
        return {"src": url, "local": False, "original_url": url}

    note_media_dir = media_root / note_id
    ensure_dir(note_media_dir)
    file_path = note_media_dir / filename
    try:
        _download_file(url, file_path)
        return {
            "src": file_path.relative_to(output_root).as_posix(),
            "local": True,
            "original_url": url,
        }
    except Exception as exc:
        download_errors.append(f"{filename}: {exc}")
        return {"src": url, "local": False, "original_url": url}


def _download_file(url, file_path):
    response = requests.get(url, stream=True, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    response.raise_for_status()
    with open(file_path, "wb") as file_obj:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                file_obj.write(chunk)


def render_report_html(task_meta, notes):
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    task_value = _format_task_value(task_meta)
    summary_items = [
        ("任务类型", task_meta.get("task_type", "-")),
        ("目标", task_value),
        ("查询关系", _format_query_mode(task_meta)),
        ("抓取数量", str(len(notes))),
        ("生成时间", generated_at),
    ]
    summary_html = "".join(
        f'<div class="summary-item"><span class="label">{escape(label)}</span><span class="value">{escape(value)}</span></div>'
        for label, value in summary_items
    )
    note_cards = "".join(_render_note_card(note, index) for index, note in enumerate(notes, start=1))
    result_message = task_meta.get("result_message")
    result_message_html = ""
    if result_message:
        result_message_html = f'<div class="notice">{escape(result_message)}</div>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(task_meta.get("title", "小红书采集报告"))}</title>
  <style>
    :root {{
      --bg: #f3f0ea;
      --surface: #fffdf9;
      --border: #ddd4c7;
      --text: #2b2722;
      --muted: #756b5f;
      --accent: #0e6b61;
      --accent-soft: #e3f0ee;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top right, #efe4d2 0, transparent 28%),
        linear-gradient(180deg, #f8f5ef 0%, var(--bg) 100%);
    }}
    .page {{
      width: min(960px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 32px 0 48px;
    }}
    .hero {{
      background: rgba(255, 253, 249, 0.92);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 28px;
      box-shadow: 0 20px 50px rgba(58, 45, 28, 0.08);
      margin-bottom: 24px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: clamp(28px, 4vw, 40px);
      line-height: 1.1;
    }}
    .hero p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 22px;
    }}
    .summary-item {{
      background: var(--accent-soft);
      border-radius: 16px;
      padding: 14px 16px;
    }}
    .notice {{
      margin-top: 16px;
      padding: 14px 16px;
      border-radius: 16px;
      background: #fff3e8;
      color: #8a4d19;
      line-height: 1.6;
      font-size: 14px;
    }}
    .label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }}
    .value {{
      display: block;
      font-size: 15px;
      font-weight: 600;
      word-break: break-word;
    }}
    .note-card {{
      background: rgba(255, 253, 249, 0.96);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 24px;
      margin-bottom: 18px;
      box-shadow: 0 18px 40px rgba(58, 45, 28, 0.08);
    }}
    .note-index {{
      display: inline-block;
      min-width: 36px;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      font-size: 12px;
      font-weight: 700;
      text-align: center;
      margin-bottom: 14px;
    }}
    .note-title {{
      margin: 0 0 10px;
      font-size: 24px;
      line-height: 1.3;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 16px;
      color: var(--muted);
      font-size: 13px;
    }}
    .meta span {{
      background: #f1ece3;
      border-radius: 999px;
      padding: 6px 10px;
    }}
    .desc {{
      white-space: pre-wrap;
      line-height: 1.8;
      font-size: 15px;
      margin-bottom: 18px;
    }}
    .gallery {{
      display: grid;
      gap: 10px;
      margin: 16px 0;
    }}
    .gallery.cols-1 {{ grid-template-columns: 1fr; }}
    .gallery.cols-2 {{ grid-template-columns: repeat(2, 1fr); }}
    .gallery.cols-3 {{ grid-template-columns: repeat(3, 1fr); }}
    .gallery img, .video-box video, .video-box img {{
      width: 100%;
      display: block;
      border-radius: 16px;
      background: #ebe4d8;
    }}
    .video-box {{
      display: grid;
      gap: 12px;
      margin: 16px 0;
    }}
    .footer-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 16px;
      font-size: 14px;
    }}
    .footer-links a {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }}
    .tags {{
      margin-top: 12px;
      color: var(--muted);
      font-size: 13px;
    }}
    .errors {{
      margin-top: 14px;
      padding: 12px 14px;
      border-radius: 14px;
      background: #fff3e8;
      color: #8a4d19;
      font-size: 13px;
      line-height: 1.6;
    }}
    @media (max-width: 640px) {{
      .page {{ width: min(100vw - 20px, 960px); padding-top: 20px; }}
      .hero, .note-card {{ padding: 18px; border-radius: 20px; }}
      .gallery.cols-3 {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <h1>{escape(task_meta.get("title", "小红书采集报告"))}</h1>
      <p>本报告按顺序展示当前任务抓取到的笔记内容，优先使用本地媒体文件，打开后即可直接阅读。</p>
      <div class="summary">{summary_html}</div>
      {result_message_html}
    </section>
    {note_cards or '<section class="note-card"><p>没有抓取到可展示的内容。</p></section>'}
  </main>
</body>
</html>
"""


def _render_note_card(note, index):
    meta = [
        note.get("nickname") or "-",
        note.get("upload_time") or "-",
        note.get("note_type") or "-",
        f"点赞 {note.get('liked_count', 0)}",
        f"收藏 {note.get('collected_count', 0)}",
        f"评论 {note.get('comment_count', 0)}",
    ]
    meta_html = "".join(f"<span>{escape(str(item))}</span>" for item in meta)
    desc = escape(note.get("desc") or "")
    tags = note.get("tags") or []
    tags_html = f'<div class="tags">标签：{" / ".join(escape(str(tag)) for tag in tags)}</div>' if tags else ""
    search_queries = note.get("search_queries") or []
    search_query_html = ""
    if search_queries:
        search_query_html = f'<div class="tags">命中关键词：{" / ".join(escape(str(query)) for query in search_queries)}</div>'
    media_html = _render_media(note)
    errors = note.get("download_errors") or []
    errors_html = ""
    if errors:
        errors_html = '<div class="errors">媒体下载失败：' + "<br>".join(escape(err) for err in errors) + "</div>"
    return f"""
    <article class="note-card">
      <div class="note-index">#{index}</div>
      <h2 class="note-title">{escape(note.get("title") or "无标题")}</h2>
      <div class="meta">{meta_html}</div>
      <div class="desc">{desc}</div>
      {media_html}
      {search_query_html}
      {tags_html}
      <div class="footer-links">
        <a href="{escape(note.get("note_url") or "#")}" target="_blank" rel="noreferrer">查看原始链接</a>
        <a href="{escape(note.get("home_url") or "#")}" target="_blank" rel="noreferrer">作者主页</a>
      </div>
      {errors_html}
    </article>
    """


def _render_media(note):
    assets = note.get("report_assets") or {}
    if note.get("note_type") == "图集":
        images = [item for item in assets.get("images", []) if item and item.get("src")]
        if not images:
            return ""
        if len(images) == 1:
            cols_class = "cols-1"
        elif len(images) <= 4:
            cols_class = "cols-2"
        else:
            cols_class = "cols-3"
        image_html = "".join(
            f'<a href="{escape(item["src"])}" target="_blank" rel="noreferrer"><img loading="lazy" src="{escape(item["src"])}" alt="{escape(note.get("title") or "图片")}"></a>'
            for item in images
        )
        return f'<section class="gallery {cols_class}">{image_html}</section>'

    video = assets.get("video")
    cover = assets.get("cover")
    blocks = []
    if video and video.get("src"):
        blocks.append(
            f'<video controls preload="metadata" src="{escape(video["src"])}"></video>'
        )
    elif cover and cover.get("src"):
        blocks.append(
            f'<img loading="lazy" src="{escape(cover["src"])}" alt="{escape(note.get("title") or "视频封面")}">'
        )
    if video and video.get("original_url"):
        blocks.append(
            f'<div class="footer-links"><a href="{escape(video["original_url"])}" target="_blank" rel="noreferrer">打开视频地址</a></div>'
        )
    if not blocks:
        return ""
    return '<section class="video-box">' + "".join(blocks) + "</section>"


def _format_task_value(task_meta):
    queries = task_meta.get("queries") or []
    if queries:
        return " / ".join(str(query) for query in queries)
    return task_meta.get("query") or task_meta.get("url") or "-"


def _format_query_mode(task_meta):
    query_mode = task_meta.get("query_mode")
    if query_mode == "all":
        return "与"
    if query_mode == "any":
        return "或"
    return "-"
