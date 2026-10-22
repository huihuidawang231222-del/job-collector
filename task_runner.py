"""Run a collector with a persistent heartbeat and explicit exit result."""
import json,os,runpy,sys,threading,time
from pathlib import Path
from collection_safety import write_json

def run(status,script,arguments):
    runtime=Path(status).with_suffix('.runtime.json')
    record={'pid':os.getpid(),'started_at':time.time(),'state':'running'}
    done=threading.Event()
    def heartbeat():
        while not done.is_set():
            write_json(runtime,{**record,'heartbeat':time.time()})
            done.wait(2)
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    code=0
    try:
        sys.argv=[script,*arguments]
        runpy.run_path(script,run_name='__main__')
    except SystemExit as e:
        code=e.code if isinstance(e.code,int) else 1 if e.code else 0
    except BaseException as e:
        code=1;record['error']=str(e)
        raise
    finally:
        done.set();thread.join()
        record.update(state='exited',exit_code=code,finished_at=time.time(),heartbeat=time.time())
        write_json(runtime,record)
    return code

if __name__=='__main__':raise SystemExit(run(sys.argv[1],sys.argv[2],sys.argv[3:]))
