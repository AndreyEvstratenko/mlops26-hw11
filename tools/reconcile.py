"""Compare client p95 to Prometheus for a selected completed run, while TSDB exists.

First port-forward svc/prometheus 19090:9090 in a separate WSL terminal.
"""
import argparse
import json
import time
import urllib.parse
from pathlib import Path
from tools.lab import http_get, save, percentile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('run',help='e.g. results/B/hot-api-1')
    args=parser.parse_args()
    directory=Path(args.run)
    rows=[json.loads(s) for f in directory.glob('client-*.jsonl') for s in f.read_text().splitlines() if s]
    good=[r for r in rows if r['outcome']=='completed']
    if not good: raise SystemExit('No completed responses in this run')
    start=min(r['sent_wall'] for r in rows if 'sent_wall' in r)-1
    end=max(r.get('finished_wall',r.get('sent_wall',start)) for r in rows)+6
    if end>time.time(): time.sleep(end-time.time())
    width=int(end-start)+1
    pods=sorted({r['pod'] for r in good})
    selector='{pod=~'+json.dumps('|'.join(pods))+'}'
    queries={
        'p95':f'histogram_quantile(0.95,sum by(le)(increase(lab_ttfc_seconds_bucket{selector}[{width}s])))',
        'observations':f'sum(increase(lab_ttfc_seconds_count{selector}[{width}s]))',
        'buckets':f'sum by(le)(increase(lab_ttfc_seconds_bucket{selector}[{width}s]))'}
    result=dict(start=start,end=end,client_completed=len(good),client_p95=percentile([r['ttfc'] for r in good],.95),promql=queries,
        limitation='Same completed-response family and wall interval; increase extrapolates scrape boundaries. Network time and bucket interpolation differ. Inspect counts and terminal logs; not exact equality.')
    for name,q in queries.items():
        result['prometheus_'+name]=http_get('http://127.0.0.1:19090/api/v1/query?'+urllib.parse.urlencode({'query':q,'time':end}))
    # A stable, non-restarted Pod set permits a non-extrapolated endpoint delta.
    count_query=f'sum(lab_ttfc_seconds_count{selector})'
    counts={}
    for label,when in [('before',start),('after',end)]:
        response=http_get('http://127.0.0.1:19090/api/v1/query?'+urllib.parse.urlencode({'query':count_query,'time':when}))
        result['counter_'+label]=response
        vector=response.get('data',{}).get('result',[])
        counts[label]=float(vector[0]['value'][1]) if vector else None
    result['counter_endpoint_delta']=counts['after']-counts['before'] if all(v is not None for v in counts.values()) else None
    result['counter_delta_limitation']='Endpoint delta is valid here only for the identified unchanged Pod set with no restart/reset. increase remains the general reset-aware query.'
    # Join by (Pod, request ID), because standardized schedules reuse IDs across runs.
    wanted={(r['pod'],r['request_id']) for r in good}
    terminal={}
    for file in directory.parent.glob('api-*.log'):
        for line in file.read_text(encoding='utf-8',errors='replace').splitlines():
            begin=line.find('{')
            if begin<0:continue
            try:record=json.loads(line[begin:])
            except ValueError:continue
            key=(record.get('pod'),record.get('request_id'))
            if key in wanted and record.get('event')=='terminal' and record.get('outcome')=='completed' and start<=record.get('wall',0)<=end:
                terminal[key]=record
    result['matched_server_terminal_count']=len(terminal)
    result['matched_server_exact_p95']=percentile([r['ttfc'] for r in terminal.values()],.95)
    result['same_completed_request_keys']=set(terminal)==wanted
    save(directory/'reconciliation.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
