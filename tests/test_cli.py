import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import requests

from chaoxing_cli import main


def fake_request(session, method, url, **kwargs):
    body = "<p>正文</p>"
    if url.endswith("fanyalogin"):
        session.cookies.set_cookie(requests.cookies.create_cookie("u", "sample", domain=".chaoxing.com"))
        body = '{"status":true}'
    elif url.endswith("stucoursemiddle"):
        body = '<input id="workEnc" value="work">'
    elif url.endswith("cards"):
        body = '<script>mArg={"attachments":[]};</script>'
    elif url.endswith("studentcourse"):
        body = '<div class="chapter_unit"><div id="cur4">第一章</div></div>'
    elif url.endswith("activelist"):
        body = '{"result":1,"data":{"activeList":[]}}'
    elif url.endswith("addStudentWorkNew"):
        body = '{"status":true}'
    response = requests.Response()
    response.status_code = 200
    response.url = url
    response._content = body.encode()
    return response


class CliTests(unittest.TestCase):
    def test_all_command_routes_with_local_responses(self):
        page = {"text": "正文", "links": []}
        with tempfile.TemporaryDirectory() as root:
            cookies = Path(root) / "account.cookies"
            form = Path(root) / "work.form"
            form.write_text("answer1=A&pyFlag=")
            har = Path(root) / "sample.har"
            har.write_text('{"log":{"entries":[]}}')
            calls = [
                (["login"], {"message": "登录成功", "cookies": str(cookies)}),
                (["space"], page),
                (["courses"], []),
                (["exams"], page),
                (["chapters", "1", "2", "3"], [{"chapter": "4", "title": "第一章", "jobs": ""}]),
                (["tasks", "1", "2", "3", "4", "--card", "1"], {"attachments": []}),
                (["activities", "1", "2", "3"], []),
                (["assignments", "1", "2", "3"], page),
                (["work", "1", "2", "3", "4", "work-5", "k", "e"], page),
                (["resources", "1", "2", "3", "--folder", "4", "--enc", "e"], page),
                (["detail", "https://i.chaoxing.com/item"], page),
                (["discussions", "https://i.chaoxing.com/list"], page),
                (["har", str(har)], []),
                (["submit", str(form)], {"method": "POST", "url": "https://mooc1.chaoxing.com/mooc-ans/work/addStudentWorkNew",
                                         "fields": ["answer1", "pyFlag"], "sent": False}),
                (["submit", str(form), "--send"], {"status": True}),
            ]
            with patch.object(requests.Session, "request", fake_request), patch("builtins.input", return_value="user"), \
                    patch("getpass.getpass", return_value="pass"):
                for arguments, expected in calls:
                    argv = ["chaoxing-cli", "--cookies", str(cookies), *arguments]
                    with self.subTest(command=arguments), patch("sys.argv", argv), redirect_stdout(io.StringIO()) as out:
                        self.assertEqual(main(), 0)
                        self.assertEqual(json.loads(out.getvalue()), expected)
