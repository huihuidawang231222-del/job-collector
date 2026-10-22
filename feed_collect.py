"""One-task bulk acceptance: distinct full JDs committed and read back from SQLite."""
import argparse,json,hashlib,time,uuid
from collections import Counter
from pathlib import Path
from datetime import datetime,timezone
from core import ROOT,save,load,job_id
from official_careers import canonical,matches
from public_feeds import lever_config,read_lever_page,normalize_lever,documented_lever_policy
from collection_safety import CollectionGuard,SafetyStop,single_collector,write_json
DATA=ROOT/'data';STATUS=DATA/'feed-task.json';STOP=DATA/'feed-stop'

def metrics(rows):
    city=[r for r in rows if matches(r,'','广州')]
    return {'saved_unique':len(rows),'complete_jd':sum(len(r.get('jd',''))>=80 for r in rows),
      'unique_urls':len({canonical(r['url']) for r in rows}),'unique_source_ids':len({(r['source_provider'],r['career_entry'],r['source_job_id']) for r in rows}),
      'guangzhou':len(city),'guangzhou_related':sum(matches(r,'数据分析,GIS,运营分析,analyst','广州') for r in rows),
      'companies':dict(Counter(r['company'] for r in rows))}

@single_collector(DATA)
def run(args):
    started=time.monotonic();task_id=uuid.uuid4().hex;STOP.unlink(missing_ok=True)
    sources=json.loads(Path(args.sources).read_text(encoding='utf-8'))
    if not isinstance(sources,list) or not 1<=len(sources)<=30:raise ValueError('来源为1至30项数组')
    if not 1<=args.target<=1000 or not 1<=args.pages<=5:raise ValueError('目标1—1000，每来源分页1—5')
    for source in sources:lever_config(source['url'])
    # Reuse daily API host budgets across all employer boards, not one guard per company.
    guards={};reports=[];candidates={};network_requests=0
    existing={job_id(r):r for r in load()}
    write_json(STATUS,{'state':'running','task_id':task_id,'target':args.target,'message':'读取官方公开岗位列表'})
    for source in sources:
        if STOP.exists():break
        config=lever_config(source['url']);host=config['api']
        guard=guards.setdefault(host,CollectionGuard(host,DATA,policy=documented_lever_policy))
        seen_ids=set();examined=0;eligible=0;requests=0
        try:
            for index in range(args.pages):
                if STOP.exists():break
                posts,api_url,size=read_lever_page(config,index*200,200,guard)
                network_requests+=1;requests+=1;new_ids=0
                for post in posts:
                    ident=str(post.get('id',''))
                    if ident in seen_ids:continue
                    seen_ids.add(ident);new_ids+=1;examined+=1
                    row=normalize_lever(post,source)
                    if not row or not matches(row,args.keyword,args.city):continue
                    key=job_id(row)
                    if key in existing and existing[key].get('jd') and not args.refresh:continue
                    row.update(batch_task_id=task_id,search_keyword=args.keyword)
                    candidates.setdefault(key,row);eligible+=1
                if len(posts)<200 or not new_ids:break
                if len(candidates)>=args.target:break
            reports.append(dict(company=source.get('company'),examined=examined,eligible=eligible,requests=requests,state='completed'))
        except Exception as e:
            reports.append(dict(company=source.get('company'),examined=examined,eligible=eligible,requests=requests,state='protected' if isinstance(e,SafetyStop) else 'failed',message=str(e)))
        write_json(STATUS,{'state':'running','task_id':task_id,'target':args.target,'eligible_unique':len(candidates),'sources':reports})
    # Prioritize explicitly Guangzhou locations for a broad capacity test; never relabel other cities.
    selected=sorted(candidates.values(),key=lambda r:(not matches(r,'','广州'),not matches(r,'数据分析,GIS,运营分析,analyst',''),r['company'],r['source_job_id']))[:args.target]
    if STOP.exists():selected=[]
    added,updated,skipped=save(selected) if selected else (0,0,0)
    # Only current-task records count; old DB rows and attempted writes do not count toward acceptance.
    stored=[r for r in load() if r.get('batch_task_id')==task_id]
    stats=metrics(stored)
    passed=(not STOP.exists() and stats['saved_unique']>=args.target and stats['complete_jd']==stats['saved_unique'] and stats['unique_urls']==stats['saved_unique'] and stats['unique_source_ids']==stats['saved_unique'] and not skipped)
    report={'task_id':task_id,'state':'stopped' if STOP.exists() else 'passed' if passed else 'incomplete','acceptance_passed':passed,
       'target':args.target,'filters':{'city':args.city or '不限地区','keyword':args.keyword or '不限岗位类型'},'metrics':stats,
       'writes':{'added':added,'updated':updated,'skipped':skipped},'network_requests':network_requests,'elapsed_seconds':round(time.monotonic()-started,2),
       'sources':reports,'finished_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
       'manifest':[{'url':r['url'],'company':r['company'],'title':r['title'],'location':r['location'],'source_job_id':r['source_job_id'],'jd_chars':len(r['jd']),'jd_sha256':hashlib.sha256(r['jd'].encode()).hexdigest()} for r in stored]}
    directory=DATA/'runs'/task_id;directory.mkdir(parents=True,exist_ok=True)
    write_json(directory/'acceptance.json',report);write_json(STATUS,report)
    (directory/'jobs.json').write_text(json.dumps(stored,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--sources',default=str(ROOT/'feed_sources.json'));parser.add_argument('--target',type=int,default=100)
    parser.add_argument('--keyword',default='数据分析,GIS,运营分析,analyst');parser.add_argument('--city',default='广州')
    parser.add_argument('--pages',type=int,default=2);parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    try:
        result=run(args);print(json.dumps({k:v for k,v in result.items() if k!='manifest'},ensure_ascii=False,indent=2))
        raise SystemExit(0 if result['acceptance_passed'] else 2)
    except Exception as e:write_json(STATUS,{'state':'failed','message':str(e)});raise
