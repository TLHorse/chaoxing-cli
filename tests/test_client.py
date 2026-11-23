import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from chaoxing import AuthenticationError, ChaoxingClient, preview_submission


def response(url, body, status=200):
    result = requests.Response()
    result.url = url
    result.status_code = status
    result.encoding = "utf-8"
    result._content = body.encode()
    return result


class ClientTests(unittest.TestCase):
    def test_login_isolation_and_cookie_round_trip(self):
        def post(session, url, **kwargs):
            session.cookies.set_cookie(requests.cookies.create_cookie("u", "abc", domain=".chaoxing.com"))
            return response(url, '{"status":true}')

        with tempfile.TemporaryDirectory() as root, ChaoxingClient() as client, ChaoxingClient() as other:
            path = Path(root) / "account" / "cookies.txt"
            with patch.object(requests.Session, "post", post):
                client.login("user", "pass", cookie_path=path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            original = path.read_bytes()
            with patch.object(requests.Session, "post", return_value=response("", '{"status":false}')):
                with self.assertRaises(AuthenticationError):
                    client.login("bad", "bad", cookie_path=path)
            self.assertEqual(path.read_bytes(), original)
            with ChaoxingClient.from_cookies(path) as saved:
                self.assertEqual([c.value for c in saved.session.cookies], ["abc"])
            self.assertEqual([c.value for c in client.session.cookies], ["abc"])
            self.assertFalse(list(other.session.cookies))

    def test_course_query_keeps_browser_fields_and_folders(self):
        entry = response("https://mooc2-ans.chaoxing.com/interaction",
                         '<input id="filterFid" value="fid"><ul class="file-list"><li fileid="7"></li></ul>')
        item = response("", '<div class="course"><span class="course-name" title="经济学"></span>'
                            '<a href="?cpi=3"></a><input class="courseId" value="1">'
                            '<input class="clazzId" value="2"></div>')
        with ChaoxingClient() as client, patch.object(client, "fetch", side_effect=[entry, item, item]) as fetch:
            rows = client.list_courses()
        self.assertEqual([r["folder"] for r in rows], ["0", "7"])
        self.assertEqual(rows[0], dict(title="经济学", course="1", clazz="2", cpi="3", folder="0"))
        self.assertEqual(fetch.call_args.kwargs["data"]["fid"], "fid")
        self.assertEqual(fetch.call_args.kwargs["headers"]["Referer"], entry.url)

    def test_preview_and_send_preserve_duplicate_answers(self):
        form = "pyFlag=&answer1=A&answer1=B"
        with ChaoxingClient() as client, patch.object(client, "fetch") as fetch:
            self.assertFalse(preview_submission(form)["sent"])
            fetch.assert_not_called()
            fetch.return_value = response("", json.dumps({"status": True}))
            self.assertTrue(client.submit_assignment(form)["status"])
            self.assertEqual(fetch.call_args.kwargs["data"], [("pyFlag", ""), ("answer1", "A"), ("answer1", "B")])
