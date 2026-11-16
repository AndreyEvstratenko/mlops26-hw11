"""Four publication/export charts from measured data, using separate units/axes."""
from collections import Counter, defaultdict
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1]/'.runtime/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from tools.lab import RESULTS, summarize


def build(groups, lines):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
        'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'figure.facecolor':'white'})
    target=RESULTS/'figures'; target.mkdir(exist_ok=True)
    files=[]
    def save(fig,name):
        fig.savefig(target/name,dpi=160,bbox_inches='tight',facecolor='white')
        plt.close(fig); files.append(name)
    def ready(rec):
        pods=[p for p in rec.get('pods',{}).get('items',[]) if p['metadata'].get('labels',{}).get('app')=='api']
        return sum(any(c.get('type')=='Ready' and c.get('status')=='True' for c in p['status'].get('conditions',[])) for p in pods)

    cluster=lines(RESULTS/'A/cluster.jsonl')
    if cluster:
        origin=cluster[0]['wall']; xs=[(r['wall']-origin)/60 for r in cluster]
        eps=[sum(e.get('conditions',{}).get('ready') is True for s in r.get('endpoints',{}).get('items',[]) if s['metadata'].get('labels',{}).get('kubernetes.io/service-name')=='api' for e in s.get('endpoints',[])) for r in cluster]
        fig,ax=plt.subplots(2,1,figsize=(11,6),sharex=True,layout='constrained')
        ax[0].step(xs,[ready(r) for r in cluster],where='post',label='Ready Pod',color='#116e65')
        ax[0].step(xs,eps,where='post',label='Готовые EndpointSlice',color='#d18a28',linestyle='--')
        ax[0].set(ylabel='Количество',title='A. Прогрев, выпуск, откат и аварийное завершение'); ax[0].legend(ncol=2)
        for name,rows in groups.items():
            if not name.startswith('A/'):continue
            subset=[r for r in rows if r.get('ttfc') is not None]
            ax[1].scatter([(r['sent_wall']-origin)/60 for r in subset],[r['ttfc'] for r in subset],s=7,label=name.split('/')[-1],alpha=.65)
        ax[1].set(ylabel='TTFC, с',xlabel='Минуты от начала опыта A'); ax[1].legend(fontsize=7,ncol=3)
        save(fig,'01-rollout.png')

    hot=groups.get('B/hot-api-sticky-1',[])
    if hot:
        origin=min(r['scheduled_wall'] for r in hot)
        fig,ax=plt.subplots(2,1,figsize=(11,6),sharex=True,layout='constrained')
        for i,pod in enumerate(sorted({r.get('pod') for r in hot if r.get('pod')})):
            rows=[r for r in hot if r.get('pod')==pod and r.get('ttfc') is not None]
            label=f'Pod {i+1}: {sum(r.get("pod")==pod for r in hot)} запросов'
            ax[0].scatter([r['sent_wall']-origin for r in rows],[r['ttfc'] for r in rows],s=9,alpha=.6,label=label)
            ax[1].scatter([r['sent_wall']-origin for r in rows],[r.get('queue_seconds',0) for r in rows],s=9,alpha=.6,label=pod)
        ax[0].set(ylabel='TTFC, с',title='B. ClientIP: 80% трафика от одного IP, повтор 1'); ax[0].legend(fontsize=8)
        ax[1].set(ylabel='Ожидание в очереди, с',xlabel='Секунды от начала нагрузки'); ax[1].legend(fontsize=7)
        save(fig,'02-hot-pod.png')

    if any(n.startswith('B/') for n in groups):
        fig,ax=plt.subplots(2,2,figsize=(11,7),layout='constrained')
        for col,traffic in enumerate(['uniform','hot']):
            for j,policy in enumerate(['api','api-sticky']):
                ss=[summarize(groups[f'B/{traffic}-{policy}-{i}']) for i in range(1,4) if f'B/{traffic}-{policy}-{i}' in groups]
                x=np.arange(1,len(ss)+1)+(j-.5)*.3
                label='Обычный Service' if policy=='api' else 'ClientIP'
                ax[0,col].bar(x,[s['ttfc_p95'] or 0 for s in ss],width=.28,label=label)
                ax[1,col].bar(x,[100*s['error_fraction'] for s in ss],width=.28,label=label)
            ax[0,col].set(title='Равномерный трафик' if traffic=='uniform' else 'Горячий клиент (80%)',ylabel='p95 успешных, с',xticks=[1,2,3]); ax[0,col].legend(fontsize=8)
            ax[1,col].set(ylabel='Неуспешные запросы, %',xlabel='Номер повтора',xticks=[1,2,3])
        save(fig,'03-policies.png')

    cluster=lines(RESULTS/'C/cluster.jsonl')
    if cluster:
        origin=cluster[0]['wall']; xs=[(r['wall']-origin)/60 for r in cluster]
        fig,ax=plt.subplots(3,1,figsize=(11,8),sharex=True,layout='constrained')
        ax[0].step(xs,[ready(r) for r in cluster],where='post',label='Ready Pod',color='#116e65')
        desired=[]
        for r in cluster:
            h=r.get('hpa',{}).get('items',[])
            desired.append(h[0].get('status',{}).get('desiredReplicas',float('nan')) if h else float('nan'))
        ax[0].step(xs,desired,where='post',label='HPA desired',color='#d18a28',linestyle='--')
        ax[0].set(ylabel='Реплики',title='C. Масштабирование, нагрузка и CPU'); ax[0].legend()
        for name,rows in groups.items():
            if not name.startswith('C/'):continue
            bins=Counter(int((r['sent_wall']-origin)//5) for r in rows if r.get('sent_wall'))
            ax[1].plot([(i*5+2.5)/60 for i in sorted(bins)],[bins[i]/5 for i in sorted(bins)],label=name.split('/')[-1])
        ax[1].set(ylabel='Отправлено, запросов/с'); ax[1].legend(fontsize=7,ncol=2)
        points=defaultdict(list)
        for r in lines(RESULTS/'C/prometheus.jsonl'):
            for item in r.get('cpu',{}).get('data',{}).get('result',[]):
                try:points[item['metric'].get('pod','unknown')].append(((r['wall']-origin)/60,float(item['value'][1])*1000))
                except (ValueError,KeyError):pass
        for pod,pts in points.items():ax[2].plot([p[0] for p in pts],[p[1] for p in pts],label=pod,alpha=.8)
        ax[2].axhline(110,color='#9c562b',linestyle='--',linewidth=1,label='Цель HPA: среднее 110m на Pod')
        ax[2].set(ylabel='CPU, millicores',xlabel='Минуты от начала C'); ax[2].legend(fontsize=6,ncol=2)
        save(fig,'04-hpa.png')
    return files
