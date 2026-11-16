"""Audit schedules, raw evidence and outcome accounting without rerunning workloads."""
import json
from collections import Counter
from pathlib import Path
from tools.lab import ROOT, RESULTS, save


def rows(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8-sig').splitlines() if s.strip()]


def main():
    checks=[]
    def check(name,passed,details):
        checks.append(dict(name=name,passed=bool(passed),details=details))
        print(('PASS ' if passed else 'FAIL ')+name)
    total=0
    for folder in sorted(RESULTS.glob('*/*')):
        if not folder.is_dir():continue
        files=sorted(folder.glob('client-*.jsonl'))
        if not files:continue
        records=[r for p in files for r in rows(p)]
        total+=len(records)
        name=folder.relative_to(RESULTS).as_posix()
        schedule=json.loads((folder/'schedule.json').read_text(encoding='utf-8'))
        ids=[s['request_id'] for batch in schedule for s in batch]
        actual=[r['request_id'] for r in records]
        check(name+' planned/recorded',Counter(ids)==Counter(actual) and len(actual)==len(set(actual)),dict(planned=len(ids),recorded=len(actual)))
        check(name+' complete requires done/chunks',all(r.get('status')==200 and r.get('chunks')==r['body']['chunks'] and r.get('ttfc') is not None and 0<=r['ttfc']<=r['duration'] for r in records if r['outcome']=='completed'),dict(completed=sum(r['outcome']=='completed' for r in records)))
        if name.startswith('B/'):
            observed={r.get('client_ip') for r in records if r.get('client_ip')}
            check(name+' four observed source IPs',len(observed)==4,sorted(observed))
            check(name+' generator kept all requests',not any(r['outcome']=='not_sent' for r in records),dict(Counter(r['outcome'] for r in records)))
            if '-api-sticky-' in name:
                mapping={client:{r.get('pod') for r in records if r['client']==client and r.get('pod')} for client in {r['client'] for r in records}}
                check(name+' ClientIP mapping preserved',all(len(pods)==1 for pods in mapping.values()),{c:sorted(v) for c,v in mapping.items()})
        check(name+' outcomes exhaustive',all(r['outcome'] in {'completed','rejected','aborted','timeout','transport_error','not_sent'} for r in records),dict(Counter(r['outcome'] for r in records)))
    for traffic in ['uniform','hot']:
        schedules=[]
        for policy in ['api','api-sticky']:
            for repeat in range(1,4):
                path=RESULTS/f'B/{traffic}-{policy}-{repeat}/schedule.json'
                if path.exists():schedules.append(json.loads(path.read_text()))
        check('B '+traffic+' same schedule in six runs',len(schedules)==6 and all(s==schedules[0] for s in schedules),dict(found=len(schedules)))
        if schedules:
            offsets=sorted(s['offset'] for b in schedules[0] for s in b)
            spacing=offsets[1]-offsets[0]
            duration=offsets[-1]-offsets[0]+spacing
            check('B '+traffic+' >=120s and four clients',duration>=120-1e-8 and len(schedules[0])==4 and all(schedules[0]),dict(duration=duration,client_counts=list(map(len,schedules[0]))))
            if traffic=='hot':
                check('B hot 80% from client 0',abs(len(schedules[0][0])/sum(map(len,schedules[0]))-.8)<1e-8,dict(counts=list(map(len,schedules[0]))))
    rollout=RESULTS/'A/rollout-A-B'
    if rollout.exists():
        records=[r for p in rollout.glob('client-*.jsonl') for r in rows(p)]
        commands=rows(ROOT/'evidence/commands.jsonl')
        starts=[c['wall'] for c in commands if 'modelVersion=B' in c['argv'] and 'neverReady=true' not in c['argv']]
        long=[r for r in records if r['body'].get('chunks')==40 and r['body'].get('chunk_delay')==1]
        check('A long stream crosses rollout',any(r['sent_wall']<t<r['finished_wall'] for r in long for t in starts),dict(long_streams=len(long),B_release_times=starts))
        check('A normal rollout zero losses/5xx',bool(records) and all(r['outcome']=='completed' and r['status']==200 for r in records),dict(Counter(r['outcome'] for r in records)))
    reconcile_path=RESULTS/'B/hot-api-1/reconciliation.json'
    rec=json.loads(reconcile_path.read_text(encoding='utf-8')) if reconcile_path.exists() else {}
    check('Client/server completed request set matches',rec.get('same_completed_request_keys') and rec.get('client_completed')==rec.get('matched_server_terminal_count')==rec.get('counter_endpoint_delta'),{k:rec.get(k) for k in ['client_completed','matched_server_terminal_count','counter_endpoint_delta']})
    evidence_checks=[c for p in RESULTS.glob('*/checks.jsonl') for c in rows(p)]
    check('Required integration checks',len(evidence_checks)>=15 and all(c['passed'] for c in evidence_checks),dict(total=len(evidence_checks),passed=sum(c['passed'] for c in evidence_checks)))
    for phase in ['A','B','C']:
        path=RESULTS/phase/'prometheus.jsonl'
        record=rows(path) if path.exists() else []
        available={metric:sum(bool(r.get(metric,{}).get('data',{}).get('result')) for r in record) for metric in ['cpu','ready','waiting','ttfc_p95']}
        check(phase+' observed metrics',bool(record) and all(available.values()),available)
    check('Four exported PNG charts',len(list((RESULTS/'figures').glob('*.png')))==4,{p.name:p.stat().st_size for p in (RESULTS/'figures').glob('*.png')})
    csv_path=RESULTS/'requests.csv'
    if csv_path.exists():
        import csv
        with csv_path.open(encoding='utf-8-sig',newline='') as f:count=sum(1 for _ in csv.DictReader(f))
        check('CSV count matches JSONL',count==total,dict(csv=count,jsonl=total))
    save(ROOT/'evidence/audit.json',dict(total_requests=total,checks=checks,passed=sum(c['passed'] for c in checks),failed=[c['name'] for c in checks if not c['passed']]))
    if any(not c['passed'] for c in checks):raise SystemExit(1)


if __name__=='__main__':main()
