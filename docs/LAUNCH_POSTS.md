# Job Collector 岗位收集箱｜本地求职工作台 / Local Job Research Workspace

## 中文

找工作时，岗位散落在不同网站，JD、简历和分析结果也很难一起管理。我做了一个在本机运行的工具：**Job Collector 岗位收集箱**。

它可以读取已接入的雇主公开岗位接口、尝试解析企业招聘页面，把岗位存入本地 SQLite，按地点和关键词筛选，再导出 CSV/JSON。支持文字型 PDF 简历解析，也可在确认发送范围后，用自己的第三方模型 API 分析单个岗位。

这次更新重点解决“到底有没有在运行”：7 个选项卡、自动刷新的进度和心跳、明确的结束原因，以及自动备份后清空岗位表。

本机已实测单任务获取并保存 100 条不同岗位，约 34 秒、4 次公开 API 请求。这个结果不限地区和岗位类型，不代表任意网站或筛选条件都能拿到 100 条。访问限制和验证码不会绕过。

如果你想把自己的岗位资料整理在本机，欢迎试用、提 issue，告诉我哪里不好用。

项目与安装说明：https://github.com/huihuidawang231222-del/job-collector

#求职工具 #Python #Streamlit #岗位管理 #独立开发

## English

Job hunting leaves a lot of scattered tabs, job descriptions and notes. I built **Job Collector**, a local workspace to keep them together.

It reads supported public employer job feeds, attempts structured extraction from company career pages, and stores jobs in local SQLite. Filter by location and keywords, export CSV/JSON, extract text from PDF resumes, and optionally analyze one job using your own third-party AI API after confirming what to send.

The latest update focuses on visibility: seven tabs, automatically refreshed progress and heartbeats, explicit stop reasons, and backups before clearing the working jobs table.

In a live Windows test, one task saved 100 distinct jobs through the public Lever API in about 34 seconds using four requests. This was an unfiltered capacity test, not a promise of 100 matching jobs for every city, role or website. Access restrictions and verification are respected.

If a local job research workspace sounds useful, give it a try. Feedback and issues are welcome—especially where the workflow feels confusing.

Code and setup: https://github.com/huihuidawang231222-del/job-collector

#Python #Streamlit #JobSearch #BuildInPublic
