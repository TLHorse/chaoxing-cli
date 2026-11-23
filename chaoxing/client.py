"""Synchronous client for the Chaoxing student web interface."""

import base64
import json
import os
import re
import tempfile
import time
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


DEFAULT_COOKIES = Path.home() / ".config" / "chaoxing-cli" / "cookies.txt"


class ChaoxingError(ValueError):
    """The platform rejected a request or returned an unusable response."""


class AuthenticationError(ChaoxingError):
    """The supplied credentials or session cannot authenticate this user."""


def default_cookie_path() -> Path:
    """Resolve the same cookie path as the command line."""
    return Path(os.environ.get("CHAOXING_COOKIES") or DEFAULT_COOKIES).expanduser()


def encrypt_login(value):
    import pyaes

    key = b"u2oh6Vu^HWe4_AES"
    encoder = pyaes.Encrypter(pyaes.AESModeOfOperationCBC(key, iv=key))
    data = encoder.feed(value.encode("utf-8")) + encoder.feed()
    return base64.b64encode(data).decode("ascii")


def _save_cookies(jar: MozillaCookieJar, path: Path) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        temp_path = Path(tmp.name)
    try:
        jar.save(str(temp_path), ignore_discard=True)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def checked(url):
    parts = urlsplit(url)
    host = parts.hostname or ""
    if (parts.scheme != "https" or parts.username is not None or parts.password is not None
            or parts.port not in (None, 443) or not (host == "chaoxing.com" or host.endswith(".chaoxing.com"))):
        raise ValueError("地址必须是超星域名下的 HTTPS URL")
    return url


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


def _submission_fields(form: str) -> list[tuple[str, str]]:
    pairs = parse_qsl(form.strip(), keep_blank_values=True, strict_parsing=True)
    fields = dict(pairs)
    if fields.get("pyFlag") != "" or not any(re.fullmatch(r"answer\d+", k) for k in fields):
        raise ValueError("需要完整的章节作业提交表单，含空 pyFlag 和 answer<题号> 字段")
    return pairs


def preview_submission(form: str) -> dict:
    """Validate a URL-encoded chapter assignment locally and list its field names."""
    pairs = _submission_fields(form)
    return {"method": "POST", "url": SUBMIT, "fields": [k for k, _ in pairs], "sent": False}


class ChaoxingClient:
    """One synchronous requests session for one user. Close it or use a with block."""

    def __init__(self, cookies: str | Path | None = None):
        jar = MozillaCookieJar()
        if cookies is not None:
            path = Path(cookies).expanduser()
            if not path.is_file():
                raise AuthenticationError("请先登录或指定已有 Cookie 文件")
            jar.load(str(path), ignore_discard=True)
        self.session = requests.Session()
        self.session.cookies = jar

    @classmethod
    def from_cookies(cls, path: str | Path | None = None) -> "ChaoxingClient":
        """Load a Netscape cookie file. The default follows the CLI configuration."""
        return cls(default_cookie_path() if path is None else path)

    def close(self) -> None:
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def login(self, username: str, password: str, *, cookie_path: str | Path | None = None) -> None:
        """Authenticate this client. Supply cookie_path to persist the new session."""
        username = username.strip()
        if not username or not password:
            raise ValueError("请输入账号和密码")
        form = dict(fid="-1", uname=encrypt_login(username), password=encrypt_login(password),
                    refer="https%3A%2F%2Fi.chaoxing.com", t=True, forbidotherlogin=0,
                    validate="", doubleFactorLogin=0, independentId=0)
        jar = MozillaCookieJar()
        with requests.Session() as session:
            session.cookies = jar
            response = session.post("https://passport2.chaoxing.com/fanyalogin", data=form,
                                    timeout=(8, 25), allow_redirects=False)
            if response.status_code == 401:
                raise AuthenticationError("登录凭据无效")
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict) or result.get("status") is not True:
                reason = (result.get("msg2") or result.get("msg")) if isinstance(result, dict) else None
                raise AuthenticationError(reason or "登录未成功，请核对账号或查看网页登录提示")
            if not len(jar):
                raise AuthenticationError("服务器未返回会话 Cookie")
        if cookie_path is not None:
            _save_cookies(jar, Path(cookie_path).expanduser())
        self.session.cookies = jar

    def fetch(self, url, *, params=None, data=None, headers=None):
        for _ in range(8):
            checked(url)
            if (urlsplit(url).hostname or "").startswith("passport"):
                raise AuthenticationError("会话已失效，请重新登录")
            response = self.session.request("POST" if data is not None else "GET", url,
                                            params=params, data=data, headers=headers,
                                            timeout=(8, 25), allow_redirects=False)
            if response.is_redirect:
                if data is not None:
                    raise ChaoxingError("POST 收到重定向，请查看网页版状态")
                url = urljoin(response.url, response.headers["Location"])
                params = None
                continue
            if response.status_code == 401:
                raise AuthenticationError("登录凭据无效，请重新登录")
            if not response.ok:
                raise ChaoxingError(f"服务器返回 HTTP {response.status_code}")
            if "charset=" not in response.headers.get("Content-Type", "").lower():
                response.encoding = "utf-8"
            if 'type="password"' in response.text or 'id="formLogin"' in response.text:
                raise AuthenticationError("返回了登录页，请重新登录")
            return response
        raise ChaoxingError("页面重定向次数过多")

    def get_space(self) -> dict:
        return page(self.fetch(SPACE))

    def get_detail(self, url: str) -> dict:
        return page(self.fetch(url))

    def list_discussions(self, url: str) -> dict:
        return self.get_detail(url)

    def submit_assignment(self, form: str) -> dict:
        """Send a URL-encoded chapter assignment once. Use preview_submission for a dry run."""
        pairs = _submission_fields(form)
        resp = self.fetch(SUBMIT, data=pairs, headers={"Origin": MOOC, "X-Requested-With": "XMLHttpRequest"})
        result = resp.json()
        if not isinstance(result, dict):
            raise ChaoxingError("提交未获确认：响应格式异常")
        if result.get("status") not in (True, 1, "true"):
            raise ChaoxingError("提交未获确认：" + str(result.get("msg", "未知响应")))
        return result

    def list_courses(self) -> list[dict]:
        result = []
        browser_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }
        entry = self.fetch(INTERACTION, headers=browser_headers)
        doc = soup(entry)
        folders = doc.select("ul.file-list > li[fileid]")
        origin = urlsplit(entry.url)
        list_headers = {
            **browser_headers,
            "Origin": f"{origin.scheme}://{origin.netloc}",
            "Referer": entry.url,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "text/html, */*; q=0.01",
        }
        form = {
            "courseType": 1,
            "query": "",
            "pageHeader": field(doc, "#stuPageHeader"),
            "single": field(doc, "#single"),
            "superstarClass": field(doc, "#superstarClass") or "0",
            "isFirefly": int(field(doc, "#isFirefly") == "1"),
            "courseLevelLabelId": 0,
            "fid": field(doc, "#filterFid"),
            "from": field(doc, "#from"),
        }
        for folder in dict.fromkeys(["0"] + [f["fileid"] for f in folders]):
            resp = self.fetch(COURSE + "/visit/courselistdata",
                                data={**form, "courseFolderId": folder}, headers=list_headers)
            for node in soup(resp).select("div.course"):
                href = field(node, "a[href*='cpi=']", "href")
                result.append(dict(title=field(node, ".course-name", "title"), course=field(node, ".courseId"),
                                   clazz=field(node, ".clazzId"), cpi=parse_qs(urlsplit(href).query).get("cpi", [""])[0],
                                   folder=folder))
        return result

    def list_exams(self) -> list | dict:
        resp = self.fetch(EXAMS)
        rows = soup(resp).select("tr.dataTr")
        return [[cell.get_text(" ", strip=True) for cell in row.select("td")] for row in rows] if rows else page(resp)

    def get_work(self, course: str, clazz: str, cpi: str, chapter: str, job: str, ktoken: str, enc: str) -> dict:
        params = dict(api=1, workId=job.removeprefix("work-"), jobid=job, originJobId=job,
                      needRedirect="true", skipHeader="true", knowledgeid=chapter, ktoken=ktoken,
                      cpi=cpi, ut="s", clazzId=clazz, type="", enc=enc, mooc2=1, courseid=course)
        return page(self.fetch(MOOC + "/mooc-ans/api/work", params=params))

    def list_activities(self, course: str, clazz: str, fid: str) -> list:
        params = dict(fid=fid, courseId=course, classId=clazz,
                      showNotStartedActive=0, _=int(time.time() * 1000))
        result = self.fetch(ACTIVE, params=params).json()
        if result.get("result") != 1:
            raise ChaoxingError(str(result.get("errorMsg", "活动查询失败")))
        return result["data"]["activeList"]

    def get_tasks(self, course: str, clazz: str, cpi: str, chapter: str, *, card: int = 0) -> dict:
        params = dict(courseid=course, clazzid=clazz, cpi=cpi, ut="s")
        params.update(knowledgeid=chapter, num=card, mooc2=1, v="2025-0424-1038-3")
        resp = self.fetch(MOOC + "/mooc-ans/knowledge/cards", params=params)
        marker = re.search(r"\bmArg\s*=\s*(?=\{)", resp.text)
        if marker:
            return json.JSONDecoder().raw_decode(resp.text[marker.end():])[0]
        return page(resp)

    def list_resources(self, course: str, clazz: str, cpi: str, *,
                       folder: str | None = None, enc: str | None = None) -> dict:
        if bool(folder) != bool(enc):
            raise ValueError("folder 和 enc 需要同时提供")
        params = dict(courseid=course, clazzid=clazz, cpi=cpi, ut="s")
        if folder:
            params.update(dataId=folder, enc=enc)
        return page(self.fetch(COURSE + "/coursedata/stu-datalist", params=params))

    def _course_context(self, course: str, clazz: str, cpi: str):
        params = dict(courseid=course, clazzid=clazz, cpi=cpi, ut="s", ismooc2=1, v=2)
        middle = self.fetch(MOOC + "/visit/stucoursemiddle", params=params)
        return middle.url, soup(middle)

    def list_assignments(self, course: str, clazz: str, cpi: str) -> dict:
        middle_url, doc = self._course_context(course, clazz, cpi)
        enc, openc = field(doc, "#enc"), field(doc, "#openc")
        work = field(doc, "#workEnc")
        if not work:
            raise ChaoxingError("课程页缺少 workEnc，请核对课程信息和访问权限")
        params = dict(courseId=course, classId=clazz, cpi=cpi, ut="s", openc=openc,
                      enc=work, stuenc=enc, t=int(time.time() * 1000), isdisplaytable=2)
        return page(self.fetch(MOOC + "/mooc2/work/list", params=params, headers={"Referer": middle_url}))

    def list_chapters(self, course: str, clazz: str, cpi: str) -> list | dict:
        middle_url, doc = self._course_context(course, clazz, cpi)
        params = dict(courseid=course, clazzid=clazz, cpi=cpi, ut="s",
                      enc=field(doc, "#enc"), openc=field(doc, "#openc"), fromMiddle=1)
        resp = self.fetch(COURSE + "/mycourse/studentcourse", params=params, headers={"Referer": middle_url})
        chapters = []
        for node in soup(resp).select(".chapter_unit [id^=cur]"):
            if re.fullmatch(r"cur\d+", node["id"]):
                chapters.append(dict(chapter=node["id"][3:], title=node.get_text(" ", strip=True),
                                     jobs=field(node, ".knowledgeJobCount")))
        return chapters or page(resp)
