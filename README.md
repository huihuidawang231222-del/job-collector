# Job Collector · 岗位收集箱

本地运行的岗位收集与求职资料整理工具：把公开岗位、完整 JD、简历文字和可选 AI 分析放在一个工作台。

A local job research workspace for public job postings, full job descriptions, PDF resume text, and optional AI analysis.

## 最新功能 / Features

- **7 个选项卡**：公开接口采集、企业官网采集、招聘平台采集、岗位表与导出、简历解析、AI 岗位分析、导入与补录。
- **看得见的任务状态**：每 2 秒刷新进度和心跳，显示完成、未达目标、异常及具体排除原因。
- **可重置的岗位表**：清空前确认并自动备份，保留分析历史和采集证据。
- **本地资料管理**：SQLite、CSV/JSON 往返导入导出、PDF 文字提取；第三方 AI 为可选功能，发送前确认。
- Seven focused tabs; live task progress, heartbeat and explicit stop reasons.
- Backup before clearing the working jobs table; collection evidence and analysis history remain separate.
- Local SQLite storage, CSV/JSON import/export, text-based PDF resume parsing, and optional third-party AI analysis with explicit consent.

## 实测范围 / Verified scope

2026-10-23 Windows 本机：**50 项测试通过**；单任务通过 Lever 公开 API 获取、保存并读回 **100 条不同岗位**，4 次请求、约 34 秒。不限地区与岗位类型，不代表 100 条广州目标岗位。Chromium 网页路径另行验证 2 页、保存 1 条岗位。

Windows validation on 2026-10-23: **50 passing tests**. One live task saved and read back **100 distinct jobs** through the public Lever API in about 34 seconds using 4 requests. This was an unfiltered capacity check, not 100 jobs in a target city or role. A separate Chromium check visited 2 pages and saved 1 job.

[详细验收 / Validation details](docs/LOCAL_ACCEPTANCE_20261023.md) · [中英文推广文案 / Launch posts](docs/LAUNCH_POSTS.md)

## 快速开始 / Quick start

需要 Python 3.10+。Windows 双击 `安装.bat`，然后双击 `启动管理界面.bat`。首次尝试建议使用公开接口采集；默认广州筛选可能得到较少结果。

Requires Python 3.10+. On Windows, run `安装.bat`, then `启动管理界面.bat`. Or use a terminal:

```bash
python -m venv .venv
# Activate .venv first, then:
pip install -r requirements.txt
python -m playwright install chromium
streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

只访问允许的公开来源，遇到 robots 限制、登录或验证时停止；不保证支持所有招聘平台。扫描版 PDF 暂不支持 OCR。AI 调用需要自己的服务配置和密钥，厂商可能收费。`data/`、简历与凭据不随源码发布。

Use permitted public sources. Collection stops for access restrictions or verification; universal job-board support is not promised. Scanned PDFs need OCR, which is not included. AI is optional and requires your own provider settings and key; provider charges may apply. Local data and credentials are excluded from this repository.

---


这是可运行的源码初版，需要安装 Python 3.10+。不是免安装 EXE，也不是已验证覆盖全部招聘平台的成品。

## Windows 使用
1. 解压到固定文件夹（不要直接在压缩包里启动）。安装 Python 时勾选 Add Python to PATH。
2. 双击 `安装.bat`，首次安装依赖，需要联网。优先使用已安装的专用 Chromium；缺少时使用本机 Edge 或 Chrome，均不存在时才下载 Chromium。
3. 双击 `启动管理界面.bat`，浏览器打开本地岗位管理界面。
4. 在管理界面输入关键词、选择平台，点击“开始自动采集”。默认广州，设置每平台最多条数和加载轮数。
5. 软件会打开浏览器并自动搜索、滚动加载、尝试点击下一页、访问详情采集JD。需要登录或验证时，在采集浏览器处理，再在管理界面点击继续。无需手动滚动。
6. 点击刷新查看任务状态与结果，按地点、待遇、JD和行业筛选并导出。停止按钮请求进程安全退出。旧的 `采集岗位.bat` 仅为手动采集备用入口。

macOS / Linux：使用终端运行 `python3 -m venv .venv`，激活环境后 `pip install -r requirements.txt`、`python -m playwright install chromium`；分别运行 `streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false` 和 `python collector.py`。Linux 有桌面环境才能打开采集浏览器。

## 支持边界
- 已加入[平台访问保护](docs/COLLECTION_SAFETY.md)。最新保护模式会拦截robots禁止的搜索路径，规则无法核实时暂停自动采集；当前BOSS搜索路径受限，其余平台规则待核。下文已有的“框架已实现”及历史测试记录不代表现在自动采集获准开放。人工浏览、补录和CSV/JSON导入仍可使用。
- 2026-10-22 本机真实测试：智联新版分栏列表可保存公开岗位名称、公司、地点和详情链接（3条）；未登录时薪资隐藏、JD需登录，不读取被裁剪的全文。BOSS、猎聘、前程无忧本次连接失败，尚未验证采集可用。
- 内置 BOSS直聘、智联、猎聘、前程无忧的 CSS 规则草案，以及标准 JobPosting JSON-LD 详情页解析。**规则尚未完成真实平台登录联调，页面改版时可能采集不到或字段不完整。** 未识别时明确报错，不伪造数据。只针对网页版，不读取手机 App。
- 自动搜索与连续加载已实现，仍需正常访问和必要的登录。验证码、访问限制由你处理。不会绕过验证、调用隐藏接口或获取非公开数据。
- 仅采集浏览器可以正常加载的岗位，达到数量/轮数上限或不再有新数据时结束；原始卡片文字一起保留，方便核对。公司和地点等字段缺失时可导出修正再导入。
- URL 相同视为同岗并更新；没有 URL 时按来源、名称、公司、地点去重。跨平台岗位暂时分别保留，避免误合并。
- 月薪解析支持 8-12K、8千-1.2万等区间；日薪、时薪、年薪、面议等不强行折算；13薪不并入月薪。双休只是岗位原文标记，不代表待遇核实。
- CSV/JSON 支持本软件导出的中文列，也支持 title（必填）, company, salary, location, source, url, benefits, raw, jd, industry_raw 等英文字段。CSV 使用 UTF-8 编码；岗位链接和前导零按文本保留。中文 CSV 的公式防护前缀在重新导入时还原。
- 相同岗位更新时，仅用非空字段替换已有值；缺失或空白的 JD、行业、福利等字段保留已有内容，不支持用空字段清空。首次采集时间保持不变，最近采集时间更新为本次保存时间。导入到新库时保留导出文件中的首次采集时间；中文导出增加福利原文、搜索关键词和详情采集错误列，旧版文件仍可导入。

## 数据与维护
岗位保存在 `data/jobs.sqlite3`。独立采集浏览器登录状态按浏览器保存在 `data/browser`、`data/browser-msedge` 或 `data/browser-chrome`，不使用日常浏览器档案，请勿分享这些目录。切换浏览器后可能需要重新登录。备份前先退出软件，再复制 data 目录。向别人分享源码时排除 data 和 .venv。管理界面仅监听本机地址。

后续接入网站时使用 JSON 导出即可。当前没有服务器费用，也不依赖付费 API；运行电脑和联网由使用者提供。

## 验证
Windows 安装后运行 `.venv\Scripts\python -m unittest discover -v`，检查薪资、去重更新、导入导出往返、数据库连接释放及 API 请求与失败处理。API 测试使用模拟响应，不代表真实模型已联通。真实平台采集需要在你的电脑上进一步联调。

## PDF 简历上传与解析

展开「上传 PDF 简历并解析」，选择文件并点击「解析简历」。使用开源 [pypdf](https://github.com/py-pdf/pypdf) 在本机提取文字，展示逐页原文和可编辑核对版，支持下载核对后的 TXT。原 PDF 不写入项目磁盘；上传与解析不调用任何模型。文件限制为10MB、20页、提取文字12000字符；加密、损坏或超限文件会报错，不静默截断。

此功能不含OCR，也不承诺保留原PDF版式。扫描图片页、无法提取文字的页会明确提示，混合型PDF也会列出缺失页码。多栏简历、特殊字体或图片中的文字可能错序或漏字，必须核对后再使用。

在「AI 岗位分析」中勾选「使用上方核对后的简历做匹配分析」，再确认发送范围，即可把核对版文字与单个岗位一起发送至所填API服务；默认不勾选。启用后，原始提取文字、核对版及文件SHA256会随分析保存在本地 analyses 表和分析JSON中，便于追溯，不会覆盖岗位或简历原文件。「清除本次简历解析」只清除当前页面解析，不删除已保存的分析记录。

## 第三方 API 岗位分析使用

在筛选结果下展开「AI 岗位分析」，选择单个岗位，填写 API Key 和可选求职偏好，确认发送范围后点击分析。Key 仅在本次本地会话中使用，不写入数据库或配置文件；请勿将密钥发到聊天或提交到 Git。

测试默认使用智谱 `glm-4.7-flash`（不要与 `glm-4.7-flashx` 混淆），Base URL 为 `https://open.bigmodel.cn/api/paas/v4`。截至 2026-10-22 查阅的[智谱官方公告](https://www.zhipuai.cn/zh/news/148)标明该型号免费调用；注册后仍需以账户权限、限流和实时定价为准。[API Key 管理](https://bigmodel.cn/usercenter/proj-mgmt/apikeys)、[官方调用文档](https://docs.bigmodel.cn/cn/guide/models/free/glm-4.7-flash)。本项目不会自动创建账户、充值或切换收费模型。

支持更换为兼容 Chat Completions 的第三方服务（HTTPS Base URL 和模型名）；不同厂商的参数兼容性需要分别验证。一次仅发送选中岗位的原文字段和求职偏好，输入总长最多32000字符，输出上限1200 tokens；超时60秒，不自动重试。失败、空响应或输出截断时不保存成功记录。

分析追加保存在同一 SQLite 数据库的 analyses 表，保留模型、服务地址、时间、用量、输入快照及正文，标注「AI分析，未经人工核实」，不会覆盖岗位原文。界面显示最近20条并可导出 JSON。当前实现为直接 API 调用，没有实现 MCP 服务。


## 分类导出
中文列按工作地点（城市、区、地点原文）、待遇（月薪上下限、薪数、福利、休息安排）、岗位JD（全文、学历、经验、技能）、行业（分类、原文、依据）组织。可导出全部CSV、JSON，或按城市、行业、休息安排分文件的ZIP。JD未能在详情页识别时显示“未获取详情”，不会把列表摘要冒充完整JD。行业只能从平台明确的行业字段归类，不按岗位名称猜测公司行业。

当前区名词表以广州为主；其它城市可保留工作地点原文。默认工资筛选仅比较可识别月薪。自动采集默认广州；其它城市可选单个平台并传入该平台城市代码，多城市选择器待补充。已有任务锁时不要重复启动。若进程意外退出，确认采集进程已关闭后删除 `data/worker.lock` 再启动。

自动采集命令示例：`python auto_collect.py --keyword 数据分析 --platforms BOSS直聘 猎聘 --limit 10 --rounds 5`。规则门禁会先判断路径；禁止或待核时只报告保护原因，不请求岗位页。不能通过提高间隔推断平台许可。

采集和管理界面可同时运行，但不要同时运行两个采集浏览器进程。完整数据库与浏览器档案不会纳入Git版本控制。


## 公司官网岗位（新增）

管理界面新增“公司官网岗位搜索”：输入关键词、城市，选择公司目录或补充官网入口。支持Playwright动态页及公开静态HTML、JSON-LD/Microdata JD提取、招聘系统租户发现、已有JD跳过及带来源的分类导出。详见 [官网采集说明及云端验证](docs/OFFICIAL_CAREERS.md)。搜索引擎发现仍为实验功能，不保证任意关键词发现全部公司。

## 单次100条验收

新增“官网公开岗位批量采集与验收”，接入Lever官方公开岗位列表接口，目标可设1—1000条。按当前任务实际保存后从数据库读回的唯一岗位计数，旧数据和重复岗位不凑数；JD、URL及来源发布ID必须齐全。详见`docs/OFFICIAL_CAREERS.md`与`docs/BATCH_ACCEPTANCE_100.json`。本次实测不限地区100条，广州11条，广州相关关键词1条；不是100条广州目标岗位。
