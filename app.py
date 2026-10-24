import io, json, subprocess, sys, zipfile, hashlib
from pathlib import Path
from classify import export_rows, enrich, EXPORT_COLUMNS
from auto_collect import DATA, STATUS, STOP, RESUME, PLATFORMS
import pandas as pd
import streamlit as st
from core import save,load
from transfer import read_import, csv_cell
from analysis_api import analyze, save_analysis, load_analyses, DEFAULT_BASE_URL, DEFAULT_MODEL
from resume_pdf import parse_resume
st.set_page_config(page_title='岗位收集箱',page_icon='💼',layout='wide')
st.title('💼 岗位收集箱')
st.caption('本地独立版 · 浏览器辅助采集 · 筛选与导出')
st.caption('四个平台规则仍待真实登录联调；自动流程已实现，成功数量以任务结果为准。')
with st.expander('官网公开岗位批量采集与验收', expanded=True):
    from feed_collect import STATUS as FEED_STATUS, STOP as FEED_STOP
    st.caption('使用Lever官方公开岗位接口批量获取完整JD，无需账号或API密钥。默认仍筛选广州；没有足够匹配岗位时明确显示数量不足。地区和关键词都留空可做跨地区容量测试。')
    feed_catalog=json.loads(Path(__file__).with_name('feed_sources.json').read_text(encoding='utf-8'))
    with st.form('bulk_feed'):
        feed_keyword=st.text_input('批量岗位关键词（逗号分隔；留空不限）',value='数据分析,GIS,运营分析,analyst')
        feed_city=st.text_input('批量岗位城市（留空不限地区）',value='广州')
        feed_choices=st.multiselect('雇主公开岗位列表',[x['company'] for x in feed_catalog],default=[x['company'] for x in feed_catalog])
        feed_target=st.number_input('单次任务验收目标（去重且有完整JD）',min_value=1,max_value=1000,value=100)
        feed_pages=st.number_input('每个雇主最多接口分页（每页最多200条）',min_value=1,max_value=5,value=2)
        feed_refresh=st.checkbox('重新读取并更新已有岗位（默认已有完整JD不计入新采集）')
        feed_launch=st.form_submit_button('开始批量采集与验收')
    if feed_launch:
        DATA.mkdir(exist_ok=True)
        chosen=[x for x in feed_catalog if x['company'] in feed_choices]
        if (DATA/'worker.lock').exists():st.error('已有采集任务运行或旧进程锁未清理')
        elif not chosen:st.error('请选择至少一个雇主')
        else:
            source_path=DATA/'feed-task-sources.json';source_path.write_text(json.dumps(chosen,ensure_ascii=False),encoding='utf-8')
            cmd=[sys.executable,str(Path(__file__).with_name('feed_collect.py')),'--sources',str(source_path),'--keyword',feed_keyword,'--city',feed_city,'--target',str(feed_target),'--pages',str(feed_pages)]
            if feed_refresh:cmd.append('--refresh')
            with (DATA/'feed-worker.log').open('a',encoding='utf-8') as log:subprocess.Popen(cmd,cwd=str(Path(__file__).parent),stdout=log,stderr=log)
            st.success('已启动。只有本次任务实际保存并从数据库读回的唯一岗位计入验收。')
    if st.button('停止批量采集'):
        DATA.mkdir(exist_ok=True);FEED_STOP.touch()
    if FEED_STATUS.exists():
        try:
            feed_state=json.loads(FEED_STATUS.read_text(encoding='utf-8'))
            st.json({k:v for k,v in feed_state.items() if k!='manifest'})
            if 'manifest' in feed_state:
                st.download_button('下载本次采集验收清单（含来源和JD校验值）',json.dumps(feed_state,ensure_ascii=False,indent=2).encode('utf-8'),'collection-acceptance.json','application/json')
        except (ValueError,OSError):st.caption('批量状态更新中')
with st.expander('公司官网岗位搜索', expanded=True):
    from official_careers import STATUS as OFFICIAL_STATUS, STOP as OFFICIAL_STOP
    st.caption('从公司招聘入口及其直接链接的网申系统提取公开JD，已有完整JD默认跳过。只将明确包含岗位地点的记录计入城市匹配。')
    catalog=json.loads(Path(__file__).with_name('official_sources.json').read_text(encoding='utf-8'))
    with st.form('official'):
        official_keyword=st.text_input('官网岗位关键词（逗号分隔，任一匹配）',value='数据分析,GIS,运营分析,analyst')
        official_city=st.text_input('岗位城市（留空查看所有地点）',value='广州')
        choices=st.multiselect('公司招聘目录',[x['company'] for x in catalog],default=[x['company'] for x in catalog if x['trust']=='公司官网招聘入口'])
        custom_company=st.text_input('补充公司名称（可选）')
        custom_url=st.text_input('补充官网招聘入口或岗位详情URL（可选）')
        official_pages=st.number_input('每家公司最多读取页面',min_value=1,max_value=20,value=8)
        discover=st.checkbox('先尝试搜索引擎发现入口（候选需核实，禁止/验证时停止搜索）')
        refresh=st.checkbox('重新检查已有完整JD（默认跳过）')
        transport=st.selectbox('官网读取方式',['browser','html'],format_func=lambda x:'浏览器动态页面' if x=='browser' else '公开静态HTML（不运行网站脚本）')
        official_launch=st.form_submit_button('开始官网搜索采集')
    if official_launch:
        from official_careers import public_url
        DATA.mkdir(exist_ok=True)
        chosen=[x for x in catalog if x['company'] in choices]
        if custom_url.strip():chosen.append({'company':custom_company.strip(),'url':custom_url.strip(),'trust':'用户提供，主体待核实'})
        if (DATA/'worker.lock').exists():st.error('已有采集任务，请先停止')
        elif not chosen:st.error('请选择公司或填写入口')
        elif any(not public_url(x['url']) for x in chosen):st.error('只支持公开网站的HTTP/HTTPS地址')
        else:
            source_path=DATA/'official-task-sources.json';source_path.write_text(json.dumps(chosen,ensure_ascii=False),encoding='utf-8')
            cmd=[sys.executable,str(Path(__file__).with_name('official_careers.py')),'--sources',str(source_path),'--keyword',official_keyword,'--city',official_city,'--pages',str(official_pages),'--transport',transport]
            if refresh:cmd.append('--refresh')
            if discover:cmd.append('--discover')
            with (DATA/'official-worker.log').open('a',encoding='utf-8') as log:subprocess.Popen(cmd,cwd=str(Path(__file__).parent),stdout=log,stderr=log)
            st.success('官网任务已启动。点击刷新查看结果。')
    if st.button('停止官网任务'):
        DATA.mkdir(exist_ok=True);OFFICIAL_STOP.touch()
    if OFFICIAL_STATUS.exists():
        try:
            official_state=json.loads(OFFICIAL_STATUS.read_text(encoding='utf-8'))
            st.json({k:v for k,v in official_state.items() if k!='jobs'})
        except (ValueError,OSError):st.caption('状态更新中')
with st.expander('自动搜索采集', expanded=True):
    with st.form('auto'):
        search=st.text_input('搜索关键词',value='数据分析')
        platforms=st.multiselect('采集平台',list(PLATFORMS),default=['BOSS直聘','猎聘'])
        st.caption('默认广州。其它城市可先选择单个平台并填写该平台城市代码。')
        code=st.text_input('城市代码（留空为广州）')
        limit=st.number_input('每平台最多岗位数',min_value=1,max_value=20,value=10)
        rounds=st.number_input('每平台最多加载轮数',min_value=1,max_value=10,value=5)
        st.caption('保护模式：先检查 robots 规则；禁止或待核路径不自动访问。单平台最多5分钟、每天40次自动页面动作，动作间隔至少10秒。以上为本工具自设上限，不是平台许可或安全保证。验证码需人工处理，重复验证/HTTP拒绝将触发冷却，重启任务不会清除。')
        details=st.checkbox('自动访问岗位详情获取完整JD（耗时更长）',value=True)
        launch=st.form_submit_button('开始自动采集')
    if launch:
        DATA.mkdir(exist_ok=True)
        if (DATA/'worker.lock').exists():st.error('已有任务运行或旧进程锁尚未清理')
        elif not search.strip() or not platforms:st.error('请填写关键词并选择平台')
        elif code and len(platforms)!=1:st.error('自定义城市代码时请选择单个平台')
        else:
            cmd=[sys.executable,str(Path(__file__).with_name('auto_collect.py')),'--keyword',search,'--platforms',*platforms,'--limit',str(limit),'--rounds',str(rounds)]
            if code:cmd+=['--city-code',code]
            if not details:cmd+=['--no-details']
            with (DATA/'worker.log').open('a',encoding='utf-8') as log:
                subprocess.Popen(cmd,cwd=str(Path(__file__).parent),stdout=log,stderr=log)
            st.success('已启动采集进程。自动搜索、滚动、翻页和保存；遇到登录验证时会暂停。')
    if STATUS.exists():
        try:
            task=json.loads(STATUS.read_text(encoding='utf-8'));st.json(task)
        except (ValueError,OSError):st.caption('状态更新中，请刷新')
    left,right=st.columns(2)
    if left.button('处理完登录/验证，继续'):
        DATA.mkdir(exist_ok=True);RESUME.touch()
    if right.button('停止采集'):
        DATA.mkdir(exist_ok=True);STOP.touch();st.info('已请求停止，将在当前页面操作结束后退出。')
with st.expander('导入 CSV / JSON 与手动补录'):
    st.caption('支持本软件导出的中文 CSV / JSON，也支持 title、company、salary、location、source、url、benefits、raw、jd、industry_raw 等英文字段。岗位名称必填；空字段保留已有内容，不用于清空。')
    f=st.file_uploader('选择文件',type=['csv','json'])
    if st.button('导入文件',disabled=f is None):
        try:
            records=read_import(f.getvalue(),f.name)
            st.success('新增 %s 条，更新 %s 条，跳过 %s 条'%save(records))
        except Exception as e: st.error(str(e))
    with st.form('manual'):
        title=st.text_input('岗位名称'); company=st.text_input('公司')
        sal=st.text_input('薪资（例如 8-12K·13薪）'); loc=st.text_input('地点',value='广州')
        url=st.text_input('岗位链接'); raw=st.text_area('岗位描述 / 福利原文')
        if st.form_submit_button('保存岗位'):
            if not title.strip(): st.error('请填写岗位名称')
            else: st.success('新增 %s 条，更新 %s 条，跳过 %s 条'%save([dict(title=title,company=company,salary=sal,location=loc,url=url,raw=raw,source='手动录入')]))
st.button('刷新数据')
rows=[enrich(r) for r in load()]
st.metric('本地岗位总数',len(rows))
selected_rows=[]
if rows:
    df=pd.DataFrame(rows).fillna('')
    for k in ['company','location','source','salary','url','raw','weekends','salary_min','salary_max']:
        if k not in df: df[k]=''
    a,b,c=st.columns(3)
    keyword=a.text_input('岗位 / 公司 / 描述关键词')
    city=b.text_input('地点包含')
    sources=c.multiselect('来源',sorted(df.source.unique()))
    industries=st.multiselect('行业分类',sorted(df.industry.unique()))
    districts=st.multiselect('工作地区',sorted(df.district.unique()))
    a,b,c=st.columns(3)
    minimum=a.number_input('月薪下限至少（元，0 不限制）',min_value=0,value=0,step=1000)
    weekends=b.checkbox('仅原文明确提到双休')
    if keyword: df=df[df[[c for c in ['title','company','raw','jd'] if c in df]].astype(str).apply(lambda x:x.str.contains(keyword,case=False,regex=False)).any(axis=1)]
    if city: df=df[df.location.str.contains(city,regex=False)]
    if sources: df=df[df.source.isin(sources)]
    if industries: df=df[df.industry.isin(industries)]
    if districts: df=df[df.district.isin(districts)]
    if minimum: df=df[pd.to_numeric(df.salary_min,errors='coerce')>=minimum]
    if weekends: df=df[df.weekends=='双休']
    st.write(f'筛选结果：{len(df)} 条。薪资未能识别的岗位，在薪资筛选时不计入。')
    st.dataframe(df,hide_index=True,column_config={'url':st.column_config.LinkColumn('岗位链接')})
    selected_rows=df.to_dict('records')
    df=pd.DataFrame(export_rows(selected_rows),columns=list(EXPORT_COLUMNS.values()))
    # Neutralize formula injection when a CSV is opened by spreadsheet software.
    safe=df.map(csv_cell)
    st.download_button('导出 CSV（Excel 可打开）',safe.to_csv(index=False).encode('utf-8-sig'),'jobs.csv','text/csv')
    st.download_button('导出 JSON（后续接入网站）',df.to_json(orient='records',force_ascii=False,indent=2).encode(),'jobs.json','application/json')

    bundle=io.BytesIO()
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('全部岗位.csv',safe.to_csv(index=False).encode('utf-8-sig'))
        for label in ['城市','行业分类','休息安排']:
            for index,(group,part) in enumerate(safe.groupby(label,dropna=False)):
                import re
                name=re.sub(r'[^\w一-鿿.-]','_',str(group))[:60] or '未说明'
                z.writestr(f'按{label}/{index}_{name}.csv',part.to_csv(index=False).encode('utf-8-sig'))
        summary=safe.groupby(['城市','行业分类'],dropna=False).size().reset_index(name='岗位数')
        z.writestr('分类统计.csv',summary.to_csv(index=False).encode('utf-8-sig'))
    st.download_button('按地点、行业、休息安排分类导出ZIP',bundle.getvalue(),'jobs-classified.zip','application/zip')

else: st.info('还没有岗位，请先自动采集、导入或手动补录。')

resume_for_analysis=None
with st.expander('上传 PDF 简历并解析', expanded=True):
    st.caption('本地解析，不调用模型；支持文字型PDF（10MB以内、最多20页、提取文字最多12000字符），扫描版暂不做OCR。原文件不写入磁盘。请核对多栏简历的阅读顺序及是否漏字。')
    resume_file=st.file_uploader('选择 PDF 简历',type=['pdf'],key='resume_upload')
    resume_digest=hashlib.sha256(resume_file.getvalue()).hexdigest() if resume_file else None
    parsed=st.session_state.get('parsed_resume')
    if parsed and (parsed['sha256']!=resume_digest or parsed['filename']!=resume_file.name):
        st.session_state.pop('parsed_resume',None);parsed=None
    if st.button('解析简历',disabled=resume_file is None):
        st.session_state.pop('parsed_resume',None);parsed=None
        try:
            with st.spinner('本地提取简历文字'):
                parsed=parse_resume(resume_file.getvalue(),resume_file.name)
            st.session_state['parsed_resume']=parsed
            st.session_state['resume_review_'+parsed['sha256']]=parsed['text']
        except ValueError as e:st.error(str(e))
    if parsed:
        st.caption(f"{parsed['filename']} · {parsed['page_count']}页 · {parsed['status']}")
        for warning in parsed['warnings']:st.warning(warning)
        with st.expander('逐页提取原文（只读）'):
            for page in parsed['pages']:
                st.caption(f"第{page['page']}页")
                st.text(page['text'] or '未提取到文字')
        reviewed=st.text_area('核对并修正简历文字（仅此版本可选用于分析）',key='resume_review_'+parsed['sha256'],max_chars=12000,height=260)
        if reviewed.strip():
            resume_for_analysis={**parsed,'reviewed_text':reviewed}
            st.download_button('下载核对后的简历文字',reviewed.encode('utf-8'),'resume-text.txt','text/plain')
        st.caption('默认不发送简历。下方勾选用于分析并确认发送后，简历原始提取文字与核对版会随分析记录保存在本地数据库及分析JSON中。')
        if st.button('清除本次简历解析'):
            st.session_state.pop('parsed_resume',None)
            st.rerun()

with st.expander('AI 岗位分析（第三方 API）', expanded=True):
    st.caption('默认智谱 glm-4.7-flash。每次只发送选中的一条岗位、求职偏好及你选择使用的简历文字，不发送数据库或浏览器登录信息。分析单独保存，不修改岗位原文。')
    if selected_rows:
        index=st.selectbox('选择岗位',range(len(selected_rows)),format_func=lambda i:f"{i+1}. {selected_rows[i]['title']} · {selected_rows[i].get('company','')} · {selected_rows[i].get('location','')}")
        selected=selected_rows[index]
    else:st.info('还没有可分析的岗位。请先在上方采集、导入或手动补录岗位；若已有岗位，请调整筛选条件。')
    if resume_for_analysis is None:st.session_state['use_resume']=False
    with st.form('analysis'):
        base_url=st.text_input('API Base URL',value=DEFAULT_BASE_URL)
        model=st.text_input('模型名称',value=DEFAULT_MODEL)
        api_key=st.text_input('API Key（仅在本次本地会话使用，不写入文件）',type='password')
        preferences=st.text_area('求职偏好（可选，不填则仅分析岗位）',max_chars=4000)
        use_resume=st.checkbox('使用上方核对后的简历做匹配分析',key='use_resume',disabled=resume_for_analysis is None)
        consent=st.checkbox('同意将选中岗位、偏好及勾选的简历文字发送给以上 API 服务')
        submitted=st.form_submit_button('分析此岗位',disabled=not selected_rows)
    if submitted:
        if not consent:st.error('请先确认发送范围')
        else:
            try:
                with st.spinner('分析中，最多等待约60秒；失败不会自动重试'):
                    record=analyze(selected,api_key,base_url,model,preferences,resume=resume_for_analysis if use_resume else None)
                    save_analysis(record)
                st.success('分析已单独保存，原始岗位未改动')
            except ValueError as e:st.error(str(e))
            except Exception:st.error('分析或保存失败，请检查本地数据库与服务配置')
    if selected_rows:
        history=load_analyses(selected)
        for record in history:
            st.caption(f"{record['created_at']} · {record['model']} · {record['verification']}")
            st.text(record['content'])
        if history:
            st.download_button('导出该岗位最近20次分析（含原文快照）',json.dumps(history,ensure_ascii=False,indent=2).encode('utf-8'),'job-analyses.json','application/json')

