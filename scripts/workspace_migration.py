#!/usr/bin/env python3
"""Trusted-operator migration CLI. Never exposed as an owner/path-selecting HTTP API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import time
from manage_codex_session import Worker,WorkerError
import workspace_quota as quota


def record_path(worker):
    return worker.root/('migration-'+hashlib.sha256(worker.principal.encode()).hexdigest()+'.json')


def read_record(worker):
    path=record_path(worker)
    if not os.path.lexists(path):return None
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o077 or info.st_size>65536:
        raise WorkerError('migration_record_invalid')
    try:
        value=json.loads(path.read_text())
        if value['owner']!=worker.principal or value['namespace']!=worker.namespace or not re.fullmatch('[a-f0-9]{32}',value['id']):raise ValueError()
        return value
    except (ValueError,TypeError,KeyError):raise WorkerError('migration_record_invalid') from None


def atomic(path,value):
    temporary=path.with_name(path.name+'.'+secrets.token_hex(8))
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:
            json.dump(value,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:temporary.unlink(missing_ok=True)


def idle(worker):
    if worker.db.execute("SELECT 1 FROM sessions WHERE owner=? AND state IN ('ready','provisioning','stopping') LIMIT 1",(worker.principal,)).fetchone():
        raise WorkerError('workspace_in_use')


def audit(worker,record,action,outcome):
    worker.db.execute('INSERT INTO authorization_audit(actor,action,target,outcome,at) VALUES(?,?,?,?,?)',(worker.principal,'migration_'+action,record['id'],outcome,time.time()));worker.db.commit()


def verify(worker,record):
    current=quota.call(worker,'migration-state')
    if (current.get('phase')!='ready' or current.get('identity')!=record.get('identity')
            or current.get('source_identity')!=record.get('source_identity')
            or current['source']['digest']!=record.get('digest') or current['target']['digest']!=record.get('digest')):
        raise WorkerError('migration_contents_changed')
    return current


def enrollment(worker,active):
    config=quota.configuration(worker)
    for key in ('owners','migrated'):
        values=set(config[key]);values.add(worker.principal) if active else values.discard(worker.principal);config[key]=sorted(values)
    atomic(worker.root/'quota-owners.json',config)


def prepare(worker):
    idle(worker)
    old=read_record(worker)
    if old and old['phase'] not in ('discarded',):
        if old['phase'] in ('prepared','active','rolled_back'):
            verify(worker,old);return old
        if old['phase']!='copying':raise WorkerError('migration_phase_invalid')
    if quota.enabled(worker):raise WorkerError('migration_owner_already_enrolled')
    record=old if old and old['phase']=='copying' else {'id':secrets.token_hex(16),'owner':worker.principal,'namespace':worker.namespace,'created':time.time(),'phase':'copying'}
    atomic(record_path(worker),record);audit(worker,record,'prepare','requested')
    try:
        current=quota.call(worker,'prepare-migration')
        record.update(phase='prepared',identity=current['identity'],source_identity=current['source_identity'],digest=current['source']['digest'],entries=current['source']['entries'],logical_bytes=current['source']['logical_bytes'])
        atomic(record_path(worker),record);audit(worker,record,'prepare','prepared')
        return record
    except Exception:
        audit(worker,record,'prepare','failed');raise


def act(worker,action,job_id,confirmation):
    expected={'cutover':'MIGRATE WORKSPACE','rollback':'ROLLBACK WORKSPACE','discard':'DISCARD STAGED COPY','finalize':'DELETE ROLLBACK COPY','abort':'ABORT STAGED COPY'}
    record=read_record(worker)
    if action not in expected or confirmation!=expected[action] or not record or job_id!=record['id']:
        raise WorkerError('migration_confirmation_invalid')
    idle(worker)
    audit(worker,record,action,'requested')
    if action=='abort':
        if quota.enabled(worker) or record['phase']!='copying':raise WorkerError('migration_phase_invalid')
        try:current=quota.call(worker,'migration-state')
        except WorkerError as exc:
            if quota.call(worker,'status').get('state')!='absent':raise
            current=None
        if current:quota.call(worker,'abort-migration',current['identity'])
        record['phase']='discarded'
    elif action=='finalize':
        if record['phase'] not in ('prepared','active','finalizing') or not quota.enabled(worker):raise WorkerError('migration_phase_invalid')
        from workspace_storage import checked_volume
        current=checked_volume(worker)
        if not current or current.get('_quota',{}).get('identity')!=record['identity']:raise WorkerError('migration_identity_changed')
        record['phase']='finalizing';atomic(record_path(worker),record)
        result=quota.call(worker,'finalize-migration',record['identity'])
        if result.get('finalized') is not True:raise WorkerError('migration_finalize_unverified')
        record['phase']='finalized'
    else:
        if record['phase'] not in ('prepared','active','rolled_back'):raise WorkerError('migration_phase_invalid')
        verify(worker,record)
        if action=='cutover':
            before=quota.configuration(worker)
            try:
                enrollment(worker,True)
                from workspace_storage import checked_volume
                if not checked_volume(worker).get('_quota'):raise WorkerError('migration_cutover_unverified')
            except Exception:
                atomic(worker.root/'quota-owners.json',before);raise
            record['phase']='active'
        elif action=='rollback':
            enrollment(worker,False);record['phase']='rolled_back'
        else:
            if quota.enabled(worker):raise WorkerError('migration_rollback_required')
            quota.remove(worker,record['identity']);record['phase']='discarded'
    atomic(record_path(worker),record);audit(worker,record,action,record['phase']);return record


def block_deletion(worker):
    record=read_record(worker)
    if record and record['phase'] not in ('finalized','discarded'):
        raise WorkerError('migration_rollback_retained')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','status','cutover','rollback','discard','finalize','abort'])
    parser.add_argument('--state-dir',default=str(Path.home()/'.local/state/gvisor-poc-worker'))
    parser.add_argument('--principal',default='local-pilot');parser.add_argument('--migration-id');parser.add_argument('--confirm')
    args=parser.parse_args()
    try:
        worker=Worker(args.state_dir,args.principal,'member')
        with worker.locked():
            result=prepare(worker) if args.action=='prepare' else read_record(worker) if args.action=='status' else act(worker,args.action,args.migration_id,args.confirm)
        print(json.dumps(result));return 0
    except WorkerError as exc:print(json.dumps({'error':str(exc)}),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
