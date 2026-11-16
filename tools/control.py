"""A disclosed conditional control: ClientIP need not overload a balanced mapping.

The three blind comparison repetitions remain unchanged. This extra run deliberately
selects a 2-client/2-client mapping using equivalent temporary ClientIP Services.
State probes do not populate the simulated prefix cache.
"""
import json
import time
from collections import Counter
from tools.lab import observe, fresh, k, probe, load, save, evidence_check, RESULTS


def main():
    with observe('controls') as directory:
        fresh()
        batches=json.loads((RESULTS/'B/input-uniform.json').read_text())
        attempts=[]
        selected=None
        services=[]
        try:
            for i in range(1,21):
                name=f'api-control-{i}'
                service=dict(apiVersion='v1',kind='Service',
                    metadata=dict(name=name,labels={'lab-control':'balanced-affinity'}),
                    spec=dict(selector={'app':'api'},ports=[dict(name='http',port=8080,targetPort='http')],
                        sessionAffinity='ClientIP',sessionAffinityConfig={'clientIP':{'timeoutSeconds':10800}}))
                k('apply','-f','-',input=json.dumps(service)); services.append(name)
                time.sleep(2)
                mapping={f'client-{j}':probe(f'http://{name}:8080/state',f'client-{j}')['body']['pod'] for j in range(4)}
                counts=Counter(mapping.values())
                attempts.append(dict(service=service,mapping=mapping,counts=dict(counts)))
                save(directory/'mapping-selection.json',dict(
                    method='Conditional control, not a blind random repetition. Select 2+2 client mapping via temporary Services with identical ClientIP settings. /state does not warm prefix cache.',
                    attempts=attempts))
                if sorted(counts.values())==[2,2]:
                    selected=name
                    break
            if selected is None:raise RuntimeError('No balanced mapping found; preserve attempts.')
            records=load(directory,'uniform-sticky-balanced',batches,selected,
                cache_start='empty after Pod replacement; backend warm; 2+2 affinity selected by /state probes')
            distribution=dict(Counter(r.get('pod') for r in records))
            evidence_check(directory,'balanced ClientIP control completes without overload',
                all(r['outcome']=='completed' for r in records) and sorted(distribution.values())==[len(records)//2,len(records)//2],
                dict(distribution=distribution,selection_attempts=len(attempts),selected_service=selected,
                    limitation='Deliberately conditioned initial mapping, not evidence that ClientIP generally balances clients.'))
        finally:
            for service in services:k('delete','service',service,'--ignore-not-found=true')


if __name__=='__main__':main()
