# chaoxing-cli

<img src="assets/chaoxing-cli.png" width="96" height="96" alt="chaoxing-cli 项目图标">

通过自己的学习通学生会话查询课程和作业。可从终端使用 `chaoxing-cli`，也可在 Python 程序中导入 `chaoxing`。本项目使用学习通网页接口。

| 文档 | 内容 |
| --- | --- |
| [CLI 使用手册](docs/cli.md) | 安装和登录、14 个命令的参数与输出、提交预览和错误排查 |
| [Python API 参考](docs/python-api.md) | 客户端生命周期、全部公开方法、返回结构、异常和后端集成示例 |

## 快速开始

在仓库根目录使用 Python 3.10 或更高版本运行：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
chaoxing-cli login
chaoxing-cli courses
```

同一环境中的 Python 程序可以复用刚保存的会话：

```python
from chaoxing import ChaoxingClient

with ChaoxingClient.from_cookies() as client:
    for course in client.list_courses():
        print(course["title"])
```

## 许可证与上游来源

CLI 和 Python 库采用 **GPL-3.0-only**。项目改写了上游的登录和课程访问流程。上游 README 同时载有与标准 GPLv3 存在冲突的禁止盈利声明，相关版本、原文和修改日期已记录在来源说明中。 [许可证全文](LICENSE) · [来源与修改说明](NOTICE)

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
