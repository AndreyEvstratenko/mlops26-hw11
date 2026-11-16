"""Read-only service routing and Grafana verification; run before B's cache reset."""
import json
import subprocess
import time
from tools.lab import K, ROOT, EVIDENCE, remote, save, http_get, obj


def main():
    trace={}
    for policy in ['api','api-sticky']:
        trace[policy]={}
        for i in range(4):
            code=("import json,urllib.request; "
                f"u='http://{policy}:8080/state'; "
                "print(json.dumps([json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'Connection':'close'}))) for _ in range(8)]))")
            trace[policy][f'client-{i}']=json.loads(remote(code,f'client-{i}'))
    save(EVIDENCE/'service-routing-smoke.json',dict(
        services=obj('get','services'),clients=obj('get','pods','-l','app=load-client'),
        proxy_mode='nftables',ip_family='IPv4',requests_per_client=8,trace=trace))
    with (EVIDENCE/'grafana-port-forward.log').open('w') as log:
        process=subprocess.Popen(K+['port-forward','svc/grafana','13000:3000'],stdout=log,stderr=log)
        try:
            for _ in range(30):
                try:
                    health=http_get('http://127.0.0.1:13000/api/health')
                    break
                except Exception:time.sleep(.5)
            else:raise RuntimeError('Grafana did not answer health request')
            dashboard=http_get('http://127.0.0.1:13000/api/dashboards/uid/lab11')
            save(EVIDENCE/'grafana-verified.json',dict(health=health,dashboard=dashboard))
            save(ROOT/'monitoring/dashboard-export.json',dashboard['dashboard'])
            print('Grafana health and provisioned dashboard verified.')
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__=='__main__':main()
