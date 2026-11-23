"""Terminal interface for the chaoxing library."""

import argparse
import getpass
import json
import sys
from pathlib import Path

import requests

from chaoxing import ChaoxingClient, default_cookie_path, har_inventory, preview_submission


def run(args):
    if args.command == "har":
        return har_inventory(args.file)
    if args.command == "submit":
        form = Path(args.form).read_text(encoding="utf-8")
        if not args.send:
            return preview_submission(form)
        with ChaoxingClient.from_cookies(args.cookies) as client:
            return client.submit_assignment(form)
    if args.command == "login":
        username = input("学习通账号：")
        password = getpass.getpass("学习通密码：")
        path = Path(args.cookies).expanduser()
        with ChaoxingClient() as client:
            client.login(username, password, cookie_path=path)
        return {"message": "登录成功", "cookies": str(path)}

    with ChaoxingClient.from_cookies(args.cookies) as client:
        operations = {
            "space": client.get_space,
            "courses": client.list_courses,
            "exams": client.list_exams,
            "chapters": client.list_chapters,
            "assignments": client.list_assignments,
            "resources": client.list_resources,
            "tasks": client.get_tasks,
            "work": client.get_work,
            "activities": client.list_activities,
            "discussions": client.list_discussions,
            "detail": client.get_detail,
        }
        params = {k: v for k, v in vars(args).items() if k not in ("command", "cookies")}
        return operations[args.command](**params)


def main():
    p = argparse.ArgumentParser(description="学习通个人空间 API 研究客户端")
    p.add_argument("--cookies", default=default_cookie_path(), help="Netscape Cookie 文件")
    sub = p.add_subparsers(dest="command", required=True)
    for name, desc in {"login":"账号密码登录并保存会话", "space":"个人空间菜单", "courses":"课程及文件夹", "exams":"考试列表",
                       "chapters":"章节", "assignments":"课程作业", "resources":"课程资料",
                       "tasks":"章节任务卡", "work":"读取章节作业", "activities":"课堂活动", "discussions":"读取讨论列表页",
                       "detail":"读取详情页", "har":"离线归纳浏览器 HAR", "submit":"章节作业提交"}.items():
        parser = sub.add_parser(name, help=desc)
        if name in ("chapters", "assignments", "resources", "tasks", "activities", "work"):
            for key in ("course", "clazz", "fid" if name == "activities" else "cpi"):
                parser.add_argument(key)
        if name == "work":
            for key in ("chapter", "job", "ktoken", "enc"):
                parser.add_argument(key)
        if name == "tasks":
            parser.add_argument("chapter")
            parser.add_argument("--card", type=int, default=0, help="卡片索引，从 0 开始")
        if name == "resources":
            parser.add_argument("--folder")
            parser.add_argument("--enc")
        if name in ("discussions", "detail"):
            parser.add_argument("url", help="浏览器中该页的完整 HTTPS 地址")
        if name == "har":
            parser.add_argument("file")
        if name == "submit":
            parser.add_argument("form", help="URL 编码的完整章节作业表单文件")
            parser.add_argument("--send", action="store_true", help="实际发送一次")
    args = p.parse_args()
    if args.command == "resources" and bool(args.folder) != bool(args.enc):
        p.error("--folder 和 --enc 需要同时提供")
    try:
        print(json.dumps(run(args), ensure_ascii=False, indent=2))
    except requests.RequestException as exc:
        print(f"网络或响应错误（{type(exc).__name__}）", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, EOFError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
