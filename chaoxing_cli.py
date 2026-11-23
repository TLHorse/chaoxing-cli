import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

MOOC = "https://mooc1.chaoxing.com"
SPACE = "https://i.chaoxing.com/base"
COURSE = "https://mooc2-ans.chaoxing.com/mooc2-ans"
INTERACTION = COURSE + "/visit/interaction"
SUBMIT = MOOC + "/mooc-ans/work/addStudentWorkNew"
EXAMS = "https://mooc1-api.chaoxing.com/exam-ans/exam/test/examcode/examlist"
ACTIVE = "https://mobilelearn.chaoxing.com/v2/apis/active/student/activelist"


def checked(url):
    parts = urlsplit(url)
    host = parts.hostname or ""
    if (parts.scheme != "https" or parts.username is not None or parts.password is not None
            or parts.port not in (None, 443) or not (host == "chaoxing.com" or host.endswith(".chaoxing.com"))):
        raise ValueError("地址必须是超星域名下的 HTTPS URL")
    return url


class Client:
    def __init__(self, cookies):
        if not cookies:
            raise ValueError("请通过 --cookies 或 CHAOXING_COOKIES 指定 Netscape Cookie 文件")
        jar = MozillaCookieJar(cookies)
        jar.load(ignore_discard=True)
        self.session = requests.Session()
        self.session.cookies = jar

    def fetch(self, url, *, params=None, data=None, headers=None):
        for _ in range(8):
            checked(url)
            if (urlsplit(url).hostname or "").startswith("passport"):
                raise ValueError("会话已失效，请重新导出登录 Cookie")
            response = self.session.request("POST" if data is not None else "GET", url,
                                            params=params, data=data, headers=headers,
                                            timeout=(8, 25), allow_redirects=False)
            if response.is_redirect:
                if data is not None:
                    raise ValueError("POST 收到重定向，请查看网页版状态")
                url = urljoin(response.url, response.headers["Location"])
                params = None
                continue
            if not response.ok:
                raise ValueError(f"服务器返回 HTTP {response.status_code}")
            if "charset=" not in response.headers.get("Content-Type", "").lower():
                response.encoding = "utf-8"
            if 'type="password"' in response.text or 'id="formLogin"' in response.text:
                raise ValueError("返回了登录页，请更新 Cookie")
            return response
        raise ValueError("页面重定向次数过多")


def soup(response):
    return BeautifulSoup(response.text, "html.parser")


def page(response):
    doc = soup(response)
    links = []
    for node in doc.select("[dataurl], [data-url], a[href], iframe[src], li[data]"):
        value = next((node.get(k) for k in ("dataurl", "data-url", "href", "src", "data") if node.get(k)), "")
        if value and not value.startswith(("javascript:", "#")):
            links.append({"title": node.get("title") or node.get_text(" ", strip=True),
                          "url": urljoin(response.url, value)})
    return {"text": doc.get_text("\n", strip=True), "links": links}


def field(node, selector, attr="value"):
    child = node.select_one(selector)
    return child.get(attr, "") if child else ""


def har_inventory(path):
    counts = Counter()
    for entry in json.loads(Path(path).read_text())["log"]["entries"]:
        req = entry["request"]
        parts = urlsplit(req["url"])
        host = parts.hostname or ""
        if host == "chaoxing.com" or host.endswith(".chaoxing.com"):
            names = tuple(sorted(parse_qs(parts.query, keep_blank_values=True)))
            counts[(req["method"], host, parts.path, names)] += 1
    return [dict(method=m, host=h, path=p, query_keys=k, count=n)
            for (m, h, p, k), n in sorted(counts.items())]


def run(a):
    if a.command == "har":
        return har_inventory(a.file)
    if a.command == "submit":
        body = Path(a.form).read_text(encoding="utf-8").strip()
        pairs = parse_qsl(body, keep_blank_values=True, strict_parsing=True)
        fields = dict(pairs)
        if fields.get("pyFlag") != "" or not any(re.fullmatch(r"answer\d+", k) for k in fields):
            raise ValueError("需要完整的章节作业提交表单，含空 pyFlag 和 answer<题号> 字段")
        if not a.send:
            return {"method": "POST", "url": SUBMIT, "fields": [k for k, _ in pairs], "sent": False}
    client = Client(a.cookies)
    if a.command == "submit":
        resp = client.fetch(SUBMIT, data=pairs, headers={"Origin": MOOC, "X-Requested-With": "XMLHttpRequest"})
        result = resp.json()
        if result.get("status") not in (True, 1, "true"):
            raise ValueError("提交未获确认：" + str(result.get("msg", "未知响应")))
        return result
    if a.command == "space":
        return page(client.fetch(SPACE))
    if a.command == "courses":
        result = []
        folders = soup(client.fetch(INTERACTION)).select("ul.file-list > li[fileid]")
        for folder in dict.fromkeys(["0"] + [f["fileid"] for f in folders]):
            resp = client.fetch(COURSE + "/visit/courselistdata", data=dict(courseType=1, courseFolderId=folder,
                                query="", superstarClass=0), headers={"Referer": INTERACTION})
            for node in soup(resp).select("div.course"):
                href = field(node, "a[href*='cpi=']", "href")
                result.append(dict(title=field(node, ".course-name", "title"), course=field(node, ".courseId"),
                                   clazz=field(node, ".clazzId"), cpi=parse_qs(urlsplit(href).query).get("cpi", [""])[0],
                                   folder=folder))
        return result
    if a.command == "exams":
        resp = client.fetch(EXAMS)
        rows = soup(resp).select("tr.dataTr")
        return [[cell.get_text(" ", strip=True) for cell in row.select("td")] for row in rows] if rows else page(resp)
    if a.command == "work":
        params = dict(api=1, workId=a.job.removeprefix("work-"), jobid=a.job, originJobId=a.job,
                      needRedirect="true", skipHeader="true", knowledgeid=a.chapter, ktoken=a.ktoken,
                      cpi=a.cpi, ut="s", clazzId=a.clazz, type="", enc=a.enc, mooc2=1, courseid=a.course)
        return page(client.fetch(MOOC + "/mooc-ans/api/work", params=params))
    if a.command in ("discussions", "detail"):
        return page(client.fetch(a.url))
    if a.command == "activities":
        result = client.fetch(ACTIVE, params=dict(fid=a.fid, courseId=a.course, classId=a.clazz,
                              showNotStartedActive=0, _=int(time.time()*1000))).json()
        if result.get("result") != 1:
            raise ValueError(str(result.get("errorMsg", "活动查询失败")))
        return result["data"]["activeList"]
    params = dict(courseid=a.course, clazzid=a.clazz, cpi=a.cpi, ut="s")
    if a.command == "tasks":
        params.update(knowledgeid=a.chapter, num=a.card, mooc2=1, v="2025-0424-1038-3")
        resp = client.fetch(MOOC + "/mooc-ans/knowledge/cards", params=params)
        marker = re.search(r"\bmArg\s*=\s*(?=\{)", resp.text)
        if marker:
            return json.JSONDecoder().raw_decode(resp.text[marker.end():])[0]
        return page(resp)
    if a.command == "resources":
        if a.folder:
            params.update(dataId=a.folder, enc=a.enc)
        return page(client.fetch(COURSE + "/coursedata/stu-datalist", params=params))
    middle = client.fetch(MOOC + "/visit/stucoursemiddle", params={**params, "ismooc2": 1, "v": 2})
    doc = soup(middle)
    enc, openc = field(doc, "#enc"), field(doc, "#openc")
    if a.command == "assignments":
        work = field(doc, "#workEnc")
        if not work:
            raise ValueError("课程页缺少 workEnc，请核对课程信息和访问权限")
        return page(client.fetch(MOOC + "/mooc2/work/list", params=dict(courseId=a.course, classId=a.clazz,
                          cpi=a.cpi, ut="s", openc=openc, enc=work, stuenc=enc,
                          t=int(time.time()*1000), isdisplaytable=2), headers={"Referer": middle.url}))
    params.update(enc=enc, openc=openc, fromMiddle=1)
    resp = client.fetch(COURSE + "/mycourse/studentcourse", params=params, headers={"Referer": middle.url})
    chapters = []
    for node in soup(resp).select(".chapter_unit [id^=cur]"):
        if re.fullmatch(r"cur\d+", node["id"]):
            chapters.append(dict(chapter=node["id"][3:], title=node.get_text(" ", strip=True),
                                 jobs=field(node, ".knowledgeJobCount")))
    return chapters or page(resp)


def main():
    p = argparse.ArgumentParser(description="学习通个人空间 API 研究客户端")
    p.add_argument("--cookies", default=os.environ.get("CHAOXING_COOKIES"), help="Netscape Cookie 文件")
    sub = p.add_subparsers(dest="command", required=True)
    for name, desc in {"space":"个人空间菜单", "courses":"课程及文件夹", "exams":"考试列表",
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
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
