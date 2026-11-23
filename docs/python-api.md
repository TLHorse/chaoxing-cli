# Python API 参考

在应用自己的 Python 3.10+ 环境中安装本地仓库，命令为 `python -m pip install /path/to/chaoxing-cli`。开发时可在仓库根目录运行 `python -m pip install -e .`。包的导入名为 `chaoxing`，所有网络方法都是同步调用。

## 使用已有会话

```python
from chaoxing import ChaoxingClient

def course_assignments(cookie_path):
    """读取指定用户每门课程的作业页。"""
    with ChaoxingClient.from_cookies(cookie_path) as client:
        return [
            {
                "title": course["title"],
                "page": client.list_assignments(course["course"], course["clazz"], course["cpi"]),
            }
            for course in client.list_courses()
        ]
```

本机 Agent 可省略 `from_cookies()` 的路径，使用 CLI 登录生成的会话。Web 后端应按已登录用户选择其专属 Cookie 文件或内存会话。应用可以捕获 `AuthenticationError` 并提示该用户重新登录。

## 登录和客户端生命周期

| 调用 | 行为与返回值 |
| --- | --- |
| `ChaoxingClient(cookies=None)` | 创建独立客户端。默认会话为空。传入字符串或 Path 时加载指定的 Netscape Cookie 文件。 |
| `ChaoxingClient.from_cookies(path=None)` | 返回加载了 Cookie 的新客户端。省略路径时使用 `default_cookie_path()`。 |
| `default_cookie_path()` | 模块函数，返回 Path。优先使用环境变量 CHAOXING_COOKIES，缺省为 ~/.config/chaoxing-cli/cookies.txt。 |
| `client.login(username, password, *, cookie_path=None)` | 使用字符串账号、密码登录，成功返回 None 并更新实例会话。提供路径时以私有文件形式原子保存 Cookie。 |
| `client.close()` | 释放 HTTP 会话资源，返回 None。使用 with 语句会自动调用。 |

```python
from chaoxing import ChaoxingClient

def list_my_courses(username: str, password: str):
    with ChaoxingClient() as client:
        client.login(username, password)
        return client.list_courses()
```

该示例把凭据交给当前请求使用，Cookie 只保存在内存。若要下次复用，可改为 `client.login(username, password, cookie_path=path)`。在异步 Web 框架中，可把整段同步网络操作放在线程池内执行。

## 查询方法

下表省略 `client.` 前缀。course、clazz、cpi 分别取自同一条课程记录，均以字符串传入。“页面”表示字典 `{"text": "...", "links": [{"title": "...", "url": "..."}]}`。其中作业截止时间等信息可能只出现在正文中。

| 方法 | 返回数据 |
| --- | --- |
| `get_space()` | 个人空间页面，含菜单链接。 |
| `list_courses()` | 课程字典列表。每项包含 title、course、clazz、cpi、folder，均为字符串。 |
| `list_chapters(course, clazz, cpi)` | 通常为 [{chapter, title, jobs}, …]。jobs 是页面提供的字符串值，缺失时为空字符串。解析不到条目时返回页面字典。 |
| `get_tasks(course, clazz, cpi, chapter, *, card=0)` | 指定章节、指定序号的任务卡字典。card 为从 0 开始的整数。找不到任务卡标记时返回页面。 |
| `list_assignments(course, clazz, cpi)` | 课程作业列表页面。可从 links 选择作业详情地址。 |
| `get_detail(url)` | 指定超星 HTTPS 详情页的正文和链接。 |
| `get_work(course, clazz, cpi, chapter, job, ktoken, enc)` | 章节作业页面。job 传任务卡的 jobid，ktoken 和 enc 取当前页面签发的值。 |
| `list_exams()` | 考试表格行组成的列表，每行是按网页列顺序排列的字符串列表。解析不到行时返回页面。 |
| `list_activities(course, clazz, fid)` | 课堂活动列表。fid 为机构 ID，条目字段由平台提供。 |
| `list_resources(course, clazz, cpi, *, folder=None, enc=None)` | 课程资料页面。查看子目录时同时传入文件夹 ID 和签名。 |
| `list_discussions(url)` | 读取指定的讨论列表 URL，返回页面。 |
| `fetch(url, *, params=None, data=None, headers=None)` | 底层请求，返回 requests.Response。data 为 None 时发送 GET，否则发送 POST。URL 和后续重定向需使用超星域名的 HTTPS 地址。 |

使用章节结果前可先判断 `isinstance(chapters, list)`，以便将平台返回的说明页展示给用户。考试也有同样的两种返回形式。

## 章节作业表单

`preview_submission(form)` 是离线函数，`client.submit_assignment(form)` 会实际发送一次。两个入口都接收 URL 编码的**字符串**，保留空字段和重复键。现有协议要求包含值为空的 pyFlag 和至少一个 answer 加数字题号的字段。

```python
from chaoxing import preview_submission

preview = preview_submission("pyFlag=&answer1=A&answer1=B")
assert preview["fields"] == ["pyFlag", "answer1", "answer1"]
assert preview["sent"] is False
```

上例仅演示编码和预览。向 `submit_assignment` 传入当前页面的完整表单后，成功时返回平台的 JSON 字典。平台未确认成功时抛出异常。请求超时可能发生在服务端已接收表单之后，应用应先核对提交记录。

## HAR 清单

`har_inventory(path)` 从本机读取浏览器 HAR 文件并返回字典列表。字段为 method、host、path、query_keys 和 count。query_keys 在 Python 中是排序后的键名元组，经 CLI 输出为 JSON 数组。仅统计超星域名，请求头、表单和查询参数值不会进入结果。

## 错误处理

| 异常 | 常见情形 |
| --- | --- |
| `chaoxing.AuthenticationError` | Cookie 文件缺失、登录遭拒、查询返回 401 或被识别为登录页。继承自 ChaoxingError。 |
| `chaoxing.ChaoxingError` | 平台拒绝请求、缺少课程所需字段或作业提交未获确认。继承自 ValueError。 |
| `requests.RequestException` | 连接失败、超时，以及 requests 报告的部分 HTTP 或响应解码错误。 |
| `ValueError`、`OSError`、`KeyError` | 参数组合无效、表单或本地文件格式有误、读写失败或缺少预期字段。 |

返回结构与底层页面有关。真实账号下的页面变体可能与仓库测试样本不同。命令行调用示例见 [CLI 使用手册](cli.md)。
