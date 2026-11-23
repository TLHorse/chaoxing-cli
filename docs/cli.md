# chaoxing-cli 使用手册

## 安装和登录

在仓库根目录，用 Python 3.10 或更高版本安装：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
chaoxing-cli login
chaoxing-cli courses
```

按提示输入学习通账号和密码。成功后，CLI 将会话保存为 Netscape Cookie 文件。默认位置是 `~/.config/chaoxing-cli/cookies.txt`。可以用 `CHAOXING_COOKIES` 指定路径，或将优先级最高的全局选项 `--cookies` 放在子命令前面：

```sh
chaoxing-cli --cookies ~/.config/chaoxing-cli/student.cookies login
chaoxing-cli --cookies ~/.config/chaoxing-cli/student.cookies courses
```

## 从课程找到作业

`courses` 返回课程数组。下面是一条示例记录，标识符均为演示值：

```json
{"title": "经济学", "course": "100", "clazz": "200", "cpi": "300", "folder": "0"}
```

用同一条记录里的三个标识符查作业。结果的 `text` 是页面正文，`links` 中含页面提供的链接。把相应的完整 HTTPS 地址传给 `detail` 可继续读取详情。查章节时，从结果的 `chapter` 取章节 ID，再用 `tasks` 查指定任务卡。

```sh
chaoxing-cli assignments 100 200 300
chaoxing-cli chapters 100 200 300
chaoxing-cli tasks 100 200 300 400 --card 0
```

## 命令索引

每行省略前缀 `chaoxing-cli`。大写词需替换为实际值，方括号表示可选项。

| 命令 | 输入与结果 |
| --- | --- |
| `login` | 交互登录，返回成功消息和所用 Cookie 文件路径。 |
| `space` | 查询个人空间，返回正文和菜单链接。 |
| `courses` | 查询根目录和课程文件夹，返回带课程名与标识符的数组。 |
| `chapters COURSE CLAZZ CPI` | 返回章节条目（chapter、title、jobs），解析不到条目时返回页面正文和链接。 |
| `tasks COURSE CLAZZ CPI CHAPTER [--card N]` | 读取一张任务卡。编号从 0 开始，默认 0。返回任务卡数据或页面正文和链接。 |
| `activities COURSE CLAZZ FID` | FID 为机构 ID。返回服务端提供的课堂活动数组。 |
| `assignments COURSE CLAZZ CPI` | 读取课程作业列表页的正文和详情链接。 |
| `detail URL` | 读取超星详情页的正文和链接。含查询参数的地址在 Shell 中应用引号包住。 |
| `work COURSE CLAZZ CPI CHAPTER JOB KTOKEN ENC` | 读取章节作业。JOB 为任务卡的 jobid，KTOKEN、ENC 使用当前页面或任务卡签发的值。 |
| `discussions URL` | 读取指定讨论列表页。URL 可取自浏览器打开讨论时的实际列表请求。 |
| `resources COURSE CLAZZ CPI [--folder ID --enc ENC]` | 返回资料页正文和链接。子文件夹 ID 和签名需要成对提供。 |
| `exams` | 读取考试列表，返回按网页列顺序排列的表格行。解析不到行时返回页面正文和链接。 |
| `submit FORM [--send]` | FORM 为 UTF-8 编码的表单文件路径。默认离线预览，加 `--send` 发送一次。 |
| `har FILE` | 离线读取浏览器导出的 HAR，按方法、超星域名、路径和查询键名分组计数。 |

## 预览与提交章节作业

下面的最小样例可以直接用来验证本地预览：

```sh
mkdir -p .private
printf '%s\n' 'pyFlag=&answer1=A' > .private/demo.form
chaoxing-cli submit .private/demo.form
```

预览返回 `method`、`url`、`fields` 和 `sent: false`。它只校验基本格式。真实提交需要当前章节作业页面提供的完整 URL 编码表单，包括隐藏参数和自己的答案。准备好实际文件后，运行 `chaoxing-cli submit .private/homework.form --send`。成功时输出平台的确认 JSON。提交超时后，先通过网页核对记录。当前支持章节作业的这一种表单协议。

## 输出与排错

查询结果写到标准输出，格式为 JSON。交互登录还会显示输入提示。错误提示写到标准错误。退出码 0 表示命令成功，1 用于已处理的网络、会话、文件或数据错误，2 用于参数解析错误。可用 `chaoxing-cli --help` 或 `chaoxing-cli resources --help` 检查参数顺序。

- 提示会话过期时，使用同一 Cookie 路径重新运行 `login`。需要学校额外认证的账号也可指定已导出的 Netscape Cookie 文件。
- 章节或考试返回 `{"text": "...", "links": [...]}` 时，先检查页面正文，再判断是否确实没有条目。
- 查询结果可能含个人数据和带签名的链接。HAR 和作业表单可保存在本机私有目录。

在自己的程序中调用这些功能，见 [Python API 参考](python-api.md)。
