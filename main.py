import argparse
import os
from datetime import datetime
from pathlib import Path

from loguru import logger

from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.common_util import load_env
from xhs_utils.data_util import download_note, handle_note_info, save_to_xlsx
from xhs_utils.report_util import write_task_bundle


SORT_MAP = {
    "general": 0,
    "latest": 1,
    "likes": 2,
    "comments": 3,
    "collects": 4,
}

NOTE_TYPE_MAP = {
    "all": 0,
    "video": 1,
    "normal": 2,
}


def note_matches_queries(note, queries, query_mode):
    haystack = " ".join(
        [
            str(note.get("title") or ""),
            str(note.get("desc") or ""),
            " ".join(str(tag) for tag in (note.get("tags") or [])),
            str(note.get("nickname") or ""),
        ]
    ).lower()
    matches = [query.lower() in haystack for query in queries]
    if query_mode == "all":
        return all(matches)
    return any(matches)


class DataSpider:
    def __init__(self):
        self.xhs_apis = XHS_Apis()

    def collect_note(self, note_url: str, cookies_str: str, proxies=None):
        note_info = None
        try:
            success, msg, note_info = self.xhs_apis.get_note_info(note_url, cookies_str, proxies)
            if success:
                note_info = note_info["data"]["items"][0]
                note_info["url"] = note_url
                note_info = handle_note_info(note_info)
        except Exception as exc:
            success = False
            msg = str(exc)
        logger.info(f"爬取笔记信息 {note_url}: {success}, msg: {msg}")
        return success, msg, note_info

    def collect_notes(self, note_urls: list, cookies_str: str, proxies=None):
        note_list = []
        for note_url in note_urls:
            success, msg, note_info = self.collect_note(note_url, cookies_str, proxies)
            if success and note_info is not None:
                note_list.append(note_info)
            else:
                logger.warning(f"跳过笔记 {note_url}: {msg}")
        return note_list

    def collect_user_note_urls(self, user_url: str, cookies_str: str, limit: int | None = None, proxies=None):
        note_urls = []
        try:
            success, msg, all_note_info = self.xhs_apis.get_user_all_notes(user_url, cookies_str, proxies)
            if success:
                logger.info(f"用户 {user_url} 作品数量: {len(all_note_info)}")
                for simple_note_info in all_note_info:
                    note_urls.append(
                        f"https://www.xiaohongshu.com/explore/{simple_note_info['note_id']}?xsec_token={simple_note_info['xsec_token']}"
                    )
            if limit is not None:
                note_urls = note_urls[:limit]
        except Exception as exc:
            success = False
            msg = str(exc)
        logger.info(f"爬取用户所有笔记 {user_url}: {success}, msg: {msg}")
        return note_urls, success, msg

    def collect_search_note_urls(
        self,
        query: str,
        require_num: int,
        cookies_str: str,
        sort_type_choice=0,
        note_type=0,
        note_time=0,
        note_range=0,
        pos_distance=0,
        geo: dict = None,
        proxies=None,
    ):
        note_urls = []
        try:
            success, msg, notes = self.xhs_apis.search_some_note(
                query,
                require_num,
                cookies_str,
                sort_type_choice,
                note_type,
                note_time,
                note_range,
                pos_distance,
                geo,
                proxies,
            )
            if success:
                notes = [note for note in notes if note["model_type"] == "note"]
                logger.info(f"搜索关键词 {query} 笔记数量: {len(notes)}")
                for note in notes:
                    note_urls.append(
                        f"https://www.xiaohongshu.com/explore/{note['id']}?xsec_token={note['xsec_token']}"
                    )
        except Exception as exc:
            success = False
            msg = str(exc)
        logger.info(f"搜索关键词 {query} 笔记: {success}, msg: {msg}")
        return note_urls, success, msg

    def spider_some_note(
        self,
        notes: list,
        cookies_str: str,
        base_path: dict,
        save_choice: str,
        excel_name: str = "",
        proxies=None,
    ):
        if save_choice in {"all", "excel"} and excel_name == "":
            raise ValueError("excel_name 不能为空")
        note_list = self.collect_notes(notes, cookies_str, proxies)
        for note_info in note_list:
            if save_choice == "all" or "media" in save_choice:
                download_note(note_info, base_path["media"], save_choice)
        if save_choice in {"all", "excel"}:
            file_path = os.path.abspath(os.path.join(base_path["excel"], f"{excel_name}.xlsx"))
            save_to_xlsx(note_list, file_path)


def build_parser():
    parser = argparse.ArgumentParser(description="小红书采集 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="按关键词搜索并导出报告")
    search_parser.add_argument("--query", required=True, nargs="+", help="一个或多个搜索关键词")
    search_parser.add_argument("--limit", type=int, default=20, help="每个关键词抓取数量")
    search_parser.add_argument(
        "--query-mode",
        choices=("any", "all"),
        default="any",
        help="多关键词关系：any 为或，all 为与",
    )
    search_parser.add_argument(
        "--sort",
        choices=tuple(SORT_MAP.keys()),
        default="general",
        help="排序方式",
    )
    search_parser.add_argument(
        "--note-type",
        choices=tuple(NOTE_TYPE_MAP.keys()),
        default="all",
        help="笔记类型",
    )
    add_common_args(search_parser)

    note_parser = subparsers.add_parser("note", help="按笔记链接导出报告")
    note_parser.add_argument("--url", required=True, help="笔记链接")
    add_common_args(note_parser)

    user_parser = subparsers.add_parser("user", help="按用户主页导出报告")
    user_parser.add_argument("--url", required=True, help="用户主页链接")
    user_parser.add_argument("--limit", type=int, default=None, help="最多抓取多少篇笔记")
    add_common_args(user_parser)

    return parser


def add_common_args(parser):
    parser.add_argument("--out", default=None, help="输出目录，默认自动生成")
    parser.add_argument(
        "--save",
        choices=("html", "media", "all"),
        default="all",
        help="html 仅报告，media/all 下载媒体并生成报告",
    )
    parser.add_argument("--proxy", default=None, help="代理地址，例如 http://127.0.0.1:7890")


def build_output_dir(command, args):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.out:
        custom_path = Path(args.out)
        parent = custom_path.parent if str(custom_path.parent) != "." else Path.cwd()
        return str((parent / f"{custom_path.name}_{timestamp}").resolve())
    output_name = f"{command}_{timestamp}"
    return os.path.abspath(os.path.join("outputs", output_name))


def parse_proxy(proxy_value):
    if not proxy_value:
        return None
    return {
        "http": proxy_value,
        "https": proxy_value,
    }


def run_cli_task(args):
    cookies_str = load_env()
    if not cookies_str:
        raise ValueError("未在 .env 中找到 COOKIES，请先配置后再运行")

    spider = DataSpider()
    proxies = parse_proxy(args.proxy)
    result_message = None

    if args.command == "search":
        note_urls = []
        note_query_map = {}
        queries = args.query
        candidate_limit = max(args.limit, 50) if args.query_mode == "all" and len(queries) > 1 else args.limit
        for query in queries:
            batch_urls, success, msg = spider.collect_search_note_urls(
                query,
                candidate_limit,
                cookies_str,
                sort_type_choice=SORT_MAP[args.sort],
                note_type=NOTE_TYPE_MAP[args.note_type],
                proxies=proxies,
            )
            if not success:
                raise RuntimeError(msg)
            for note_url in batch_urls:
                if note_url not in note_query_map:
                    note_urls.append(note_url)
                    note_query_map[note_url] = []
                note_query_map[note_url].append(query)

        task_meta = {
            "task_type": "search",
            "title": f"搜索报告：{' / '.join(queries)}",
            "query": queries[0],
            "queries": queries,
            "query_mode": args.query_mode,
            "sort": args.sort,
            "note_type": args.note_type,
        }
    elif args.command == "note":
        note_urls = [args.url]
        success, msg = True, "success"
        note_query_map = {}
        task_meta = {
            "task_type": "note",
            "title": "单篇笔记报告",
            "url": args.url,
        }
    else:
        note_query_map = {}
        note_urls, success, msg = spider.collect_user_note_urls(
            args.url,
            cookies_str,
            limit=args.limit,
            proxies=proxies,
        )
        task_meta = {
            "task_type": "user",
            "title": "用户主页报告",
            "url": args.url,
            "limit": args.limit,
        }

    if not success:
        raise RuntimeError(msg)
    if not note_urls:
        if args.command == "search":
            result_message = f"没有搜索到可抓取的笔记链接：{' / '.join(args.query)}"
        else:
            raise RuntimeError("没有获取到可抓取的笔记链接")

    output_dir = build_output_dir(args.command, args)
    logger.info(f"输出目录: {output_dir}")
    note_list = []
    if note_urls:
        note_list = spider.collect_notes(note_urls, cookies_str, proxies)

    if args.command == "search":
        if note_urls and not note_list:
            result_message = "搜索拿到了候选链接，但没有成功抓取到可用内容。"
        if args.query_mode == "all" and note_list:
            filtered_notes = [note for note in note_list if note_matches_queries(note, args.query, args.query_mode)]
            note_list = filtered_notes[: args.limit]
            if not note_list:
                result_message = (
                    f"与关系没有匹配结果：{' / '.join(args.query)}。可尝试增大 --limit，或改用 --query-mode any。"
                )

    if args.command != "search" and not note_list:
        raise RuntimeError("没有抓取到可用的笔记内容")

    for note in note_list:
        if args.command == "search" and args.query_mode == "all":
            note["search_queries"] = list(args.query)
        else:
            note["search_queries"] = note_query_map.get(note.get("note_url"), [])

    task_meta["output_dir"] = output_dir
    task_meta["save_mode"] = args.save
    task_meta["result_message"] = result_message
    bundle_path = write_task_bundle(task_meta, note_list, output_dir, save_mode=args.save)
    logger.info(f"报告生成完成: {bundle_path}")
    if result_message:
        logger.warning(result_message)
    print(f"报告已生成: {os.path.join(bundle_path, 'report.html')}")


def main():
    parser = build_parser()
    args = parser.parse_args()
    run_cli_task(args)


if __name__ == "__main__":
    main()
