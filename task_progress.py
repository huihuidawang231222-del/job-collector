"""Shared launch and automatically refreshed status panels for collectors."""
import json,os,subprocess,sys,time,threading
from pathlib import Path
import streamlit as st
from collection_safety import write_json

ACTIVE={'starting','running','paused'}
_workers={}
def read(path):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except (ValueError,OSError):return {}

def launch(cmd,status,log_path):
    status=Path(status);status.parent.mkdir(parents=True,exist_ok=True)
    runtime=status.with_suffix('.runtime.json')
    write_json(status,{'state':'starting','message':'正在启动采集进程，请稍候'})
    write_json(runtime,{'state':'starting','started_at':time.time(),'heartbeat':time.time()})
    try:
        with Path(log_path).open('a',encoding='utf-8') as log:
            process=subprocess.Popen([sys.executable,'-X','utf8',str(Path(__file__).with_name('task_runner.py')),str(status),*cmd[1:]],cwd=str(Path(__file__).parent),stdout=log,stderr=log)
        _workers[process.pid]=process
        def reap():
            process.wait();_workers.pop(process.pid,None)
        threading.Thread(target=reap,daemon=True).start()
        return process.pid
    except OSError as e:
        write_json(runtime,{'state':'exited','exit_code':1,'error':str(e),'finished_at':time.time()})
        return None

def snapshot(status):
    task=read(status);runtime=read(Path(status).with_suffix('.runtime.json'))
    state=task.get('state','idle');message=task.get('message','')
    if runtime.get('state')=='exited' and state in ACTIVE:
        state='failed';message=runtime.get('error') or f"采集进程已退出（退出码 {runtime.get('exit_code')}），未正常写入完成结果，请查看日志。"
    elif runtime.get('state') in ACTIVE and time.time()-runtime.get('heartbeat',0)>15:
        state='unresponsive';message='超过15秒未收到进程心跳，进程可能已退出或无响应；请查看日志，勿重复启动。'
    elif runtime.get('exit_code',0) not in (0,2) and runtime.get('state')=='exited':
        state='failed';message=runtime.get('error') or message or '后台进程异常终止，请查看日志。'
    return task,runtime,state,message

@st.fragment(run_every=2)
def panel(status,label,stop=None):
    task,runtime,state,message=snapshot(status)
    if state=='idle':st.caption(label+'：尚未启动任务');return
    reports=task.get('sources',task.get('reports',task.get('results',[])))
    if state=='finished' and any(r.get('state') in ('failed','protected','invalid_url') or r.get('protected') for r in reports):
        state='incomplete';message=message or '部分来源失败或被保护规则拦截，请查看下方各来源原因。'
    if not message and state=='incomplete':
        total=sum(r.get('examined',0) for r in reports)
        filters=task.get('filters',{})
        message=f"结束原因：所选来源已处理结束，检查{total}条，本次保存{task.get('metrics',{}).get('saved_unique',0)}条，未达到目标。地区：{filters.get('city','待核')}；关键词：{filters.get('keyword','待核')}。旧任务未记录各类排除数量，请重新运行后查看分类原因。"
    if not message and state=='stopped':message='用户请求停止，采集任务已退出。'
    title={'starting':'正在启动','running':'正在运行','paused':'等待人工处理','passed':'采集完成 · 验收通过','finished':'任务已完成','stopped':'已停止','protected':'已因访问保护停止','incomplete':'任务结束 · 未达到目标','failed':'异常终止','unresponsive':'进程失去响应'}.get(state,state)
    text=label+'：'+title
    if state in ('failed','unresponsive'):st.error(text)
    elif state in ('paused','protected','incomplete','stopped'):st.warning(text)
    elif state in ('passed','finished'):st.success(text)
    else:st.info(text+' · 页面每2秒自动更新')
    if message:st.write(message)
    if stop and Path(stop).exists() and state in ACTIVE:st.warning('已请求停止，等待当前操作结束；尚未退出。')
    if task.get('target'):
        count=task.get('metrics',{}).get('saved_unique',task.get('eligible_unique',0))
        st.progress(min(count/task['target'],1.0),text=f"符合条件的唯一岗位 {count} / 目标 {task['target']}（运行中尚待保存验收）" if state in ACTIVE else f"本次保存 {count} / 目标 {task['target']}")
    if task.get('company') or task.get('platform'):st.write('当前来源：'+str(task.get('company') or task.get('platform')))
    if task.get('pages') is not None:st.write(f"已读取 {task['pages']} 页，已匹配 {task.get('matched',0)} 条")
    if task.get('current_count') is not None:st.write(f"当前平台已保存 {task['current_count']} 条")
    if state=='incomplete' and task.get('filters'):
        st.caption('可按需要调整地区或关键词、增加雇主来源；若需重新检查已有岗位，请勾选“重新读取并更新已有岗位”。目标数量不会自动放宽筛选条件。')
    if reports:
        labels={'invalid':'信息不完整','city_mismatch':'地区不匹配','keyword_mismatch':'关键词不匹配','existing':'已有完整JD跳过','duplicate':'重复'}
        display=[]
        for report in reports:
            row={'来源':report.get('company',report.get('platform','')),'状态':{'completed':'已处理','failed':'失败','protected':'保护停止','invalid_url':'地址检查未通过'}.get(report.get('state'),report.get('state','')),'检查岗位':report.get('examined',report.get('visited',0)),'符合条件':report.get('eligible',report.get('matched',report.get('count',0))),'结束原因':report.get('message') or report.get('end_reason') or report.get('reason') or '旧记录未记录详细原因'}
            row.update({label:report.get('excluded',{}).get(key,0) for key,label in labels.items()} if 'excluded' in report else {})
            display.append(row)
        st.dataframe(display,hide_index=True)
    if runtime.get('started_at'):
        elapsed=int(runtime.get('finished_at',time.time())-runtime['started_at'])
        st.caption(f"已用时 {elapsed} 秒 · 最近心跳距今 {max(0,int(time.time()-runtime.get('heartbeat',time.time())))} 秒")
    if state not in ACTIVE and runtime.get('finished_at'):
        key=f"notice:{status}:{runtime['finished_at']}"
        if key not in st.session_state:st.toast(text);st.session_state[key]=True
    with st.expander('任务详情与日志'):
        st.json({k:v for k,v in task.items() if k not in ('jobs','manifest')})
        log_name={'feed-task.json':'feed-worker.log','official-task.json':'official-worker.log','task.json':'worker.log'}.get(Path(status).name)
        if log_name:
            path=Path(status).parent/log_name
            if path.exists():
                with path.open('rb') as stream:
                    stream.seek(max(0,path.stat().st_size-6000));st.code(stream.read().decode('utf-8',errors='replace'))
