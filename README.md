# chaoxing-cli

用自己的学习通学生会话查看个人空间和课程数据。命令输出 JSON，页面型接口提供可见文本和链接。当前目录的虚拟环境已安装命令，可直接运行 `.venv/bin/chaoxing-cli --help`。

## 开始使用

新环境使用 Python 3.10+ 安装：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

在终端运行以下命令，按提示输入学习通账号和密码。密码输入时不会回显。CLI 仅保存登录返回的 Cookie，默认文件为 `~/.config/chaoxing-cli/cookies.txt`，权限为 0600。会话过期后再次运行 login。若指定全局参数 `--cookies` 或环境变量 `CHAOXING_COOKIES`，登录和读取都会使用指定文件。需要学校单点登录或额外验证的账号仍可导入浏览器导出的 Netscape Cookie。

```sh
source .venv/bin/activate
chaoxing-cli login
chaoxing-cli courses
chaoxing-cli exams
```

从 courses 的同一条结果取 course、clazz、cpi，依次替换下面的大写参数。FID 是机构 ID。章节命令返回的 chapter 用于查询指定任务卡，卡片编号从 0 开始。

```sh
chaoxing-cli chapters COURSE CLAZZ CPI
chaoxing-cli tasks COURSE CLAZZ CPI CHAPTER --card 0
chaoxing-cli activities COURSE CLAZZ FID
chaoxing-cli assignments COURSE CLAZZ CPI
chaoxing-cli detail '作业列表返回的完整HTTPS详情URL'
chaoxing-cli work COURSE CLAZZ CPI CHAPTER JOB KTOKEN ENC
chaoxing-cli resources COURSE CLAZZ CPI
chaoxing-cli resources COURSE CLAZZ CPI --folder DATA_ID --enc ENC
chaoxing-cli discussions '从课程讨论页网络面板复制的完整HTTPS列表URL'
```

work 使用任务卡中该作业的 jobid、页面签发的 ktoken 和 enc。各课程版本的 DOM 有变化，章节或考试解析不到条目时返回正文和可发现的链接。讨论入口可能需要课程签名，网页若用 JavaScript 加载正文，应提供实际列表请求地址。资料子目录参数可从浏览器打开文件夹时的请求取得。

## 在 Python 应用中使用

在 Agent 或 Web 后端的虚拟环境里运行 `python -m pip install /Users/matianlai/Developer/chaoxing-cli`，或在本仓库中运行 `python -m pip install -e .`。安装名为 `chaoxing-cli`，Python 导入名为 `chaoxing`。

本机已经用 CLI 登录时，可以加载同一份会话。方法直接返回 Python 列表或字典。

```python
from chaoxing import ChaoxingClient

with ChaoxingClient.from_cookies() as client:
    for course in client.list_courses():
        chapters = client.list_chapters(course["course"], course["clazz"], course["cpi"])
        assignments = client.list_assignments(course["course"], course["clazz"], course["cpi"])
        print(course["title"], chapters, assignments)
```

Web 后端可以自己接收账号密码，按用户创建独立客户端。下面的调用只在内存中保留当前会话。需要持久化时，向 `login` 传入该用户专属的 `cookie_path`，以后用 `from_cookies(path)` 加载。所有请求均为同步调用，异步 Web 框架可在线程池中执行。

```python
from chaoxing import ChaoxingClient

def courses_for_user(username: str, password: str):
    with ChaoxingClient() as client:
        client.login(username, password)
        return client.list_courses()
```

| CLI 命令 | Python 接口 | 返回内容 |
| --- | --- | --- |
| login | `client.login(username, password, cookie_path=...)` | 登录后直接使用该客户端，可省略保存路径 |
| space / detail / discussions | `client.get_space()`、`client.get_detail(url)`、`client.list_discussions(url)` | 页面正文和链接 |
| courses | `client.list_courses()` | 含 title、course、clazz、cpi、folder 的课程列表 |
| chapters | `client.list_chapters(course, clazz, cpi)` | 章节列表，未解析到条目时返回页面正文和链接 |
| assignments | `client.list_assignments(course, clazz, cpi)` | 作业列表页正文和详情链接 |
| tasks | `client.get_tasks(course, clazz, cpi, chapter, card=0)` | 任务卡字典，或页面正文和链接 |
| work | `client.get_work(course, clazz, cpi, chapter, job, ktoken, enc)` | 章节作业页正文和链接 |
| resources | `client.list_resources(course, clazz, cpi)` | 资料页正文和链接，子目录可传 folder 和 enc |
| exams / activities | `client.list_exams()`、`client.list_activities(course, clazz, fid)` | 考试表格行（或页面正文和链接）、活动列表 |
| submit | `preview_submission(form)`、`client.submit_assignment(form)` | 离线预览或实际发送一次；form 是 URL 编码的表单字符串 |
| har | `har_inventory(path)` | 本地 HAR 请求统计 |

`preview_submission`、`har_inventory` 和异常类型均可从 `chaoxing` 导入。遇到会话缺失、过期或服务端拒绝登录时，可捕获 `AuthenticationError`（继承自 `ChaoxingError`）。其他平台拒绝可捕获 `ChaoxingError`，网络连接或超时等异常由 `requests.RequestException` 表示。页面正文和链接的结构为 `{"text": "...", "links": [{"title": "...", "url": "..."}]}`。

## 章节作业提交

支持原项目使用的 POST /mooc-ans/work/addStudentWorkNew。该命令接收自己填写的完整 URL 编码表单，保留重复字段、空字段和题目顺序。可在浏览器开发者工具 Network 的对应请求中查看 Payload 的原始编码，或按同版本页面的隐藏字段和自己的答案构造表单。已经成功提交的请求请勿重复发送。

```sh
chaoxing-cli submit .private/homework.form
chaoxing-cli submit .private/homework.form --send
```

第一条离线预览方法、目的地址和字段名。第二条发送一次，以服务端 JSON 的 status 和 msg 判断结果。若发生超时，先在网页核对提交记录。只适用于含空 pyFlag 和 answer<题号> 的章节作业，普通课程大作业、附件上传和其他提交协议仍需对应页面样本。

## 研究记录

| 功能 | 方法与路由 | 依据 |
| --- | --- | --- |
| 空间菜单 | GET i.chaoxing.com/base | 公开客户端记录；本次访问空间根地址时跳转 passport2 登录页 |
| 课程及文件夹 | GET /mooc2-ans/visit/interaction，POST /mooc2-ans/visit/courselistdata | 原项目 get_course_list |
| 课程上下文、章节 | GET /visit/stucoursemiddle，GET /mooc2-ans/mycourse/studentcourse | 公开客户端与原项目 get_course_point |
| 任务卡、课堂活动 | GET /mooc-ans/knowledge/cards，GET /v2/apis/active/student/activelist | 原项目 get_job_list、get_activity_list |
| 考试 | GET /exam-ans/exam/test/examcode/examlist | 公开客户端记录 |
| 作业列表、详情 | GET /mooc2/work/list，GET 页面返回的详情链接 | 公开客户端记录 |
| 章节作业读写 | GET /mooc-ans/api/work，POST /mooc-ans/work/addStudentWorkNew | 原项目 study_work |
| 资料 | GET /mooc2-ans/coursedata/stu-datalist | 公开客户端记录 |
| 讨论 | GET 页面提供的列表 URL，常见路径 /course/topic/topicList | 公开客户端记录，完整参数依赖页面 |

原项目参考版本为 be3a5bc4455eb2cc6ed1d21e5ecba4d954b77ab7。公开客户端的接口记录见 [DanMo661/xuexitong-cli](https://github.com/DanMo661/xuexitong-cli)。登录后的线上行为尚未使用个人账号验证。

要建立自己账号的接口清单，在浏览器 Network 中启用 Preserve log，依次打开目标功能并翻页，然后导出 HAR，在本机运行：

```sh
chaoxing-cli har .private/space.har
```

结果按 HTTP 方法、超星主机、路径和查询参数名称分组计数，不输出请求头、正文或查询参数值。路径本身可能含标识符。覆盖范围取决于实际访问的页面、角色和课程，静态资源也可能出现在结果中。
