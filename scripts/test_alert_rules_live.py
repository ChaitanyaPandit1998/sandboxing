#!/usr/bin/env python3
"""Live bounded egress-rule validation using a disposable session; no login/model/load test."""
import argparse
import json
import time
import uuid
from pathlib import Path
from manage_codex_session import Worker


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args();w=Worker('~/.local/state/gvisor-poc-worker');sid=None;checks={};result={}
    try:
        with w.locked():row=w.create('rule-validation-'+uuid.uuid4().hex)
        sid=row['id'];name=w.names(sid)['agent']
        code=r'''const http=require('http');const p=new URL(process.env.HTTPS_PROXY);function probe(){return new Promise(resolve=>{const r=http.request({host:p.hostname,port:p.port,method:'CONNECT',path:'example.org:443',headers:{Host:'example.org:443'}});r.setTimeout(5000,()=>{r.destroy();resolve(0)});r.on('error',()=>resolve(0));r.on('connect',(s,c)=>{resolve(s.statusCode);c.destroy()});r.end()})}(async()=>{let statuses=[];for(let i=0;i<5;i++)statuses.push(await probe());console.log(JSON.stringify(statuses))})()'''
        statuses=json.loads(w.docker('exec',name,'node','-e',code))
        checks['five_blocked_connects']=statuses==[403]*5
        deadline=time.monotonic()+65;burst=None
        while time.monotonic()<deadline:
            burst=w.db.execute("SELECT * FROM security_alerts WHERE session_id=? AND kind='egress_burst'",(sid,)).fetchone()
            if burst:break
            time.sleep(.5)
        checks['resident_burst_alert']=bool(burst and burst['status']=='open' and burst['severity']=='high')
        count=w.db.execute("SELECT COUNT(*) FROM security_events WHERE session_id=? AND kind='egress_denied'",(sid,)).fetchone()[0]
        checks['five_unique_denials_persisted']=count==5
        if burst:
            stamp=float(w.db.execute("SELECT value FROM security_meta WHERE key='last_collection'").fetchone()[0])
            deadline=time.monotonic()+65
            while time.monotonic()<deadline:
                latest=float(w.db.execute("SELECT value FROM security_meta WHERE key='last_collection'").fetchone()[0])
                if latest>stamp:break
                time.sleep(.5)
            checks['subsequent_resident_sample']=latest>stamp
            checks['resampling_did_not_duplicate_events']=w.db.execute("SELECT COUNT(*) FROM security_events WHERE session_id=? AND kind='egress_denied'",(sid,)).fetchone()[0]==5
            checks['one_burst_episode']=w.db.execute("SELECT event_count FROM security_alerts WHERE id=?",(burst['id'],)).fetchone()[0]==1
            result['alert_id']=burst['id']
        result['session_id']=sid
    except Exception:
        result['error']='live_rule_check_failed'
    finally:
        if sid:
            with w.locked():w.stop(sid)
            checks['disposable_session_stopped']=w.get(sid)['state']=='stopped'
            checks['workspace_retained']=w.exists('volume',w.volume) is not None
    result.update({'passed':bool(checks) and all(checks.values()) and 'error' not in result,'checks':checks,
                   'scope':'actual resident burst collection in a disposable session; no external site contacted, credentials, model calls or CPU/memory load; sustained resource and gap rules tested with injected unit samples'})
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    if not result['passed']:raise SystemExit(1)


if __name__=='__main__':main()
