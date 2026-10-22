# 2026-10-23 本机采集验收

- 代码：work/feed-failure-cooldown，基于 fe7374d，包含本地未提交修复。
- 浏览器：Chromium 156.0.8078.4，PLAYWRIGHT_BROWSERS_PATH=<local-browser-directory>。
- 修复：仅配置有效代理且 DNS 结果全部属于 198.18.0.0/15 时接受域名；浏览器显式使用该代理。直接私有 IP、内网 DNS 和混合 DNS 结果仍拒绝。未修改 Clash 配置。
- 回归：46 项测试通过，无跳过；git diff --check 通过。

## 100 条连续采集

本次单任务 37788e9679f646e3b2648c12f70d32b0，空白独立数据库，不限地区、不限岗位类型。4 次实际 Lever 公开 GET，33.92 秒；新增 100、更新 0、跳过 0。三个雇主：Ninja Van 79、Coates Group 15、Pattern 6。

数据库独立读回：100 行、100 个不同岗位 URL、100 个不同的来源岗位 ID。100 条 JD 均与保存的实际接口原始响应经生产解析器生成的文本一致，长度 101—10769 字符。长度只是完整性筛查，不代表雇主披露的信息充分；未逐条人工确认在招状态。11 条地址包含广州，本次不是 100 条广州目标岗位验收。

证据目录：data/qa/acceptance100-20261023-003618/，含 acceptance.json、independent-audit.json、raw-feed-1.json 至 raw-feed-4.json、jobs.sqlite3、runs/任务ID/jobs.json。测试脚本：data/qa/run_acceptance100.py。原始数据未纳入 Git。

## Chromium 网页路径

Coates Group 的 Lever 招聘页面：生产网页采集器实际访问 2 页，提取并保存 1 条岗位；结果位于上述目录 browser/official-results.json 和 browser/jobs.sqlite3。该测试使用真实网页，并非 API 数据的本地预览。100 条容量验收采用公开 API，不代表已逐页浏览 100 个岗位详情。

现有 8501 服务和原业务数据库未切换或改写。已有进程需重启才能继承用户级浏览器环境变量。
