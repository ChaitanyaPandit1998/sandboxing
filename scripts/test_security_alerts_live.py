#!/usr/bin/env python3
"""Disposable default-pilot alert fixture; no login, model traffic or workspace writes."""
import argparse
import json
import pathlib
import time
import uuid
from manage_codex_session import Worker

FIXTURE = pathlib.Path('/tmp/poc-alert-workflow-fixture.json')


def deny(worker, sid):
    code = r'''const http=require('http'),p=new URL(process.env.HTTPS_PROXY);const r=http.request({host:p.hostname,port:p.port,method:'CONNECT',path:'example.org:443',headers:{Host:'example.org:443'}});r.setTimeout(10000,()=>r.destroy());r.on('connect',(s,c)=>{console.log(s.statusCode);c.destroy();});r.on('error',()=>process.exitCode=1);r.end();'''
    return worker.docker('exec', worker.names(sid)['agent'], 'node', '-e', code) == '403'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['prepare','poll','retrigger','cleanup'])
    args=parser.parse_args(); w=Worker('~/.local/state/gvisor-poc-worker')
    if args.phase=='prepare':
        if FIXTURE.exists():raise SystemExit('existing_alert_fixture_requires_review')
        with w.locked():row=w.create('alert-validation-'+uuid.uuid4().hex)
        fixture={'session_id':row['id'],'created_at':time.time(),'expected_min_events':1}
        FIXTURE.write_text(json.dumps(fixture)); FIXTURE.chmod(0o600)
        if not deny(w,row['id']):raise SystemExit('expected_policy_denial_missing')
        print(json.dumps({'prepared':True,'session_id':row['id'],'denied_connect_status':403}))
    else:
        fixture=json.loads(FIXTURE.read_text());sid=fixture['session_id']
        if args.phase=='poll':
            until=time.monotonic()+65
            while time.monotonic()<until:
                row=w.db.execute('SELECT * FROM security_alerts WHERE session_id=? AND kind=?',(sid,'egress_denied')).fetchone()
                if row and row['event_count']>=fixture['expected_min_events']:
                    print(json.dumps({'observed':True,'alert':dict(row),'scope':'resident collection; poll does not ingest or invoke monitor'}));return
                time.sleep(.5)
            raise SystemExit('resident_alert_not_observed')
        elif args.phase=='retrigger':
            if not deny(w,sid):raise SystemExit('expected_policy_denial_missing')
            fixture['expected_min_events']=2;FIXTURE.write_text(json.dumps(fixture))
            print(json.dumps({'second_denied_connect_status':403}))
        else:
            with w.locked():w.stop(sid)
            FIXTURE.unlink()
            print(json.dumps({'disposable_session_stopped':True,'workspace_retained':w.exists('volume',w.volume) is not None}))


if __name__=='__main__':main()
