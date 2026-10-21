import re, sqlite3, json, hashlib
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
from urllib.parse import urlsplit, urlunsplit
from classify import enrich
ROOT=Path(__file__).resolve().parent
DB=ROOT/'data'/'jobs.sqlite3'
def salary(text):
    text=str(text).lower().replace(',','')
    m=re.search(r'(\d+(?:\.\d+)?)\s*([k千万]?)\s*[-~—–至]\s*(\d+(?:\.\d+)?)\s*([k千万])',text)
    if not m or any(x in text for x in ['/天','元/天','/时','元/时','/年','万/年']): return None,None
    units={'k':1000,'千':1000,'万':10000,'':1}
    a,b=float(m[1])*units[m[2] or m[4]],float(m[3])*units[m[4]]
    return (a,b) if a<=b else (None,None)
@contextmanager
def connect():
    DB.parent.mkdir(exist_ok=True)
    c=sqlite3.connect(DB)
    try:
        with c:
            c.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            yield c
    finally:
        c.close()
def job_id(row):
    url=row.get('url','')
    if url:
        u=urlsplit(url); url=urlunsplit((u.scheme,u.netloc,u.path,u.query,''))
    key=url or '|'.join(row.get(k,'') for k in ['source','title','company','location'])
    return hashlib.sha256(key.encode()).hexdigest()

def save(rows):
    added=updated=skipped=0
    with connect() as c:
        for raw in rows:
            r={k:('' if v is None else str(v)).strip() for k,v in raw.items()}
            if not r.get('title'): skipped+=1; continue
            if r.get('url'):
                u=urlsplit(r['url']); r['url']=urlunsplit((u.scheme,u.netloc,u.path,u.query,''))
            ident=job_id(r)
            old=c.execute('SELECT payload FROM jobs WHERE id=?',(ident,)).fetchone()
            previous=json.loads(old[0]) if old else {}
            # Empty or absent fields from a list capture must not erase detail data.
            r={**previous, **{k:v for k,v in r.items() if v != ''}}
            now=datetime.now(timezone.utc).isoformat(timespec='seconds')
            r['first_seen']=previous.get('first_seen') or r.get('first_seen') or now
            r['last_seen']=now
            r['salary_min'],r['salary_max']=salary(r.get('salary',''))
            text=r.get('raw','')+' '+r.get('benefits','')
            r['weekends']='双休' if '双休' in text and not any(x in text for x in ['单双休','非双休','不双休','不是双休']) else '未说明'
            r=enrich(r)
            c.execute('INSERT OR REPLACE INTO jobs VALUES (?,?)',(ident,json.dumps(r,ensure_ascii=False)))
            if old: updated+=1
            else: added+=1
    return added,updated,skipped
def load():
    with connect() as c: return [json.loads(x[0]) for x in c.execute('SELECT payload FROM jobs ORDER BY rowid DESC')]
