"""Personalize and interpret only fresh local evidence; never copy former results."""
import base64
import html
import json
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from tools.lab import ROOT, RESULTS, summarize, percentile
from tools.plots import build


def lines(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8-sig').splitlines() if s.strip()] if path.exists() else []


def table(headers,rows):
    def fmt(x):
        if x is None:return '—'
        if isinstance(x,float):return f'{x:.3f}'
        if isinstance(x,dict):return ', '.join(f'{k}: {v}' for k,v in x.items())
        return str(x)
    return '<div class="scroll"><table><tr>'+''.join('<th>'+html.escape(x)+'</th>' for x in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(fmt(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</table></div>'


def main():
    groups={}
    for folder in sorted(RESULTS.glob('*/*')):
        if folder.is_dir():
            rows=[r for p in sorted(folder.glob('client-*.jsonl')) for r in lines(p)]
            if rows:groups[folder.relative_to(RESULTS).as_posix()]=rows
    all_rows=[r for rows in groups.values() for r in rows]
    checks=[dict(c,phase=p.parent.name) for p in RESULTS.glob('*/checks.jsonl') for c in lines(p)]
    author=json.loads((ROOT/'author.json').read_text(encoding='utf-8'))
    report=(ROOT/'report.html').read_text(encoding='utf-8')
    report=report.replace('<title>ДЗ 11 — отчёт</title>','<title>ДЗ 11 — Евстратенко Андрей</title>')
    report=re.sub(r'<p class="missing">Автор, группа,.*?</p>',
        '<div class="author"><b>'+html.escape(author['name'])+'</b><br>Группа: '+html.escape(author['group'])+'<br>Локальный Kubernetes / kind / Docker Desktop / CPU</div>',report)
    report=report.replace('<h1>ДЗ 11. Сервис работает, пользователи ждут</h1>',
        '<p class="eyebrow">MLOPS · ЛАБОРАТОРНАЯ РАБОТА № 11</p><h1>Сервис работает,<br>пользователи ждут</h1>')
    css='''<style>html{background:#edf2f3}body{background:white;max-width:1140px;margin:0 auto;padding:48px 50px;color:#18343b;font:16px/1.65 system-ui,sans-serif;box-sizing:border-box}h1{font-size:38px;line-height:1.15}h2{font-size:25px;border-top:2px solid #deebe8;padding-top:24px;margin-top:40px}h3{font-size:20px}a{color:#116e65}.eyebrow{letter-spacing:.1em;font-weight:700;color:#116e65;font-size:13px}.author{background:#edf6f3;padding:18px 22px;border-left:4px solid #116e65;margin-bottom:24px}.scroll{overflow-x:auto}table{font-size:12px;table-layout:auto}th{background:#edf6f3}th,td{overflow-wrap:anywhere;padding:8px}img{width:100%;height:auto}figure{margin:26px 0}figcaption,.small{font-size:13px;color:#526b70}.missing{background:#fff2d8;border-left:4px solid #c98629}.result{background:#edf6f3;padding:18px 22px}pre{font-size:12px}@media(max-width:700px){body{padding:24px 18px}h1{font-size:29px}}@media print{html{background:white}body{padding:0;margin:0}figure,tr{break-inside:avoid}}</style>'''
    report=report.replace('</style>','</style>'+css,1)
    passed=sum(c['passed'] for c in checks)
    lead=f'<div class="result"><b>Результаты собственных прогонов.</b> Запросов: {len(all_rows):,}. Kubernetes-проверки: {passed}/{len(checks)} PASS. Локальные проверки: <a href="evidence/local-tests.txt">журнал HTTP-тестов</a>.</div>'
    lead+='<p>Сеть: kind с kube-proxy nftables, IPv4 Pod/Service, ядро WSL 5.15.167.4. Режим выбран после ошибки xt_recent в iptables. IPv6-предупреждения ядра сохранены; IPv6-трафик в опытах не используется. Docker data disk перенесён на D с разрешения автора. Журналы и ограничения: evidence/network-limits.txt и storage-change.json.</p>'
    lead+='<p>Основа — своё решение ДЗ 8–10 из <code>D:/mlops26-hw8-9-10-solution</code>. Проверка артефактов использует точную копию исходного <code>release.py</code>; сохранён вход /generate с prompt/max_new_tokens. У имитатора этот лимит означает число частей, а не токенов. Происхождение общей обвязки Helm/опытов и изменения раскрыты в <a href="PROVENANCE.md">PROVENANCE.md</a>.</p>'
    sample=groups.get('B/uniform-api-1',[])
    if sample:
        ips={}
        for row in sample:
            if row.get('client_ip'):ips.setdefault(row['client'],set()).add(row['client_ip'])
        lead+='<p>Фактические IP, наблюдаемые backend (без потери адреса клиента):</p>'+table(['Клиентский Pod','Наблюдаемый IP'],[[client,', '.join(sorted(values))] for client,values in sorted(ips.items())])
    report=report.replace('<h2>Сводка измерений</h2>',lead+'<h2>Сводка измерений</h2>')
    durations=[]
    for name,rows in groups.items():
        good=[r for r in rows if r['outcome']=='completed']
        intervals=[r['inter_chunk_mean'] for r in good if r.get('inter_chunk_mean') is not None]
        durations.append([name,len(good),percentile([r['duration'] for r in good],.5),percentile([r['duration'] for r in good],.95),len(intervals),percentile(intervals,.5),percentile(intervals,.95)])
    duration_section='<h2>Полное время ответа и интервалы частей</h2>'+table(['Прогон','N успешных','p50 полного, с','p95 полного, с','N со средним интервалом','p50 среднего ICL, с','p95 среднего ICL, с'],durations)
    duration_section+='<p>ICL здесь — средний интервал между соседними частями конкретного ответа; в таблице приведены перцентили этих средних по успешным запросам, а не перцентиль всех отдельных интервалов. Для одного chunk интервал отсутствует. В CSV явно восстановлены first_chunk_mono=sent_mono+TTFC и finished_mono=sent_mono+duration; исходные JSONL сохраняются без изменения.</p>'
    report=report.replace('<h2>Собственные проверки</h2>',duration_section+'<h2>Собственные проверки</h2>')


    # Replace the synthetic SVG layout with standard plotting and independent axes.
    pngs=build(groups,lines)
    captions={
        '01-rollout.png':'1. Ready, EndpointSlice и TTFC на общей временной оси; отказы без первой части отсутствуют в точках TTFC и учитываются отдельно в таблице исходов.',
        '02-hot-pod.png':'2. Задержка и очередь по Pod. Представлены запросы с первой частью; полный учёт отказов — в таблице и JSONL.',
        '03-policies.png':'3. Три повтора каждой комбинации при одинаковом расписании и пустом кеше после прогрева. Период поступления запросов — 120 секунд.',
        '04-hpa.png':'4. Ready, желаемое число реплик, фактическая частота отправки и CPU. После масштабирования выполнены горячий ClientIP и отдельные фазы алертов с фиксированными двумя репликами.'}
    for png in pngs:
        prefix=png.split('-')[0]
        encoded=base64.b64encode((RESULTS/'figures'/png).read_bytes()).decode()
        image=f'<figure><img src="data:image/png;base64,{encoded}" alt="{html.escape(captions[png])}"><figcaption>{html.escape(captions[png])}</figcaption></figure>'
        report=re.sub(r'<img src="results/figures/'+prefix+r'-[^" ]+\.svg"[^>]*>',lambda m:image,report)
        old_svg=RESULTS/'figures'/png.replace('.png','.svg')
        if old_svg.exists():old_svg.unlink()

    # Tables and interpretation use all repeats, with per-Pod samples retained.
    comparison=[]; summaries={}
    for traffic in ['uniform','hot']:
        for policy in ['api','api-sticky']:
            ss=[summarize(groups[f'B/{traffic}-{policy}-{i}']) for i in range(1,4) if f'B/{traffic}-{policy}-{i}' in groups]
            summaries[traffic,policy]=ss
            if not ss:continue
            p95=[s['ttfc_p95'] for s in ss if s['ttfc_p95'] is not None]
            comparison.append([traffic,policy,len(ss),f'{min(p95):.3f}–{max(p95):.3f}' if p95 else 'нет успешных',f'{min(s["error_fraction"]*100 for s in ss):.1f}–{max(s["error_fraction"]*100 for s in ss):.1f}',max(s['max_dispatch_lag'] for s in ss)])
    extra='<p>Все сравниваемые варианты B используют work=1. Фаза C использует work=8 для HPA и стимула алертов, work=4 для горячего клиента. Эти фазы C не сравниваются с B как одинаковая вычислительная нагрузка.</p><h3>Фактические результаты сравнения</h3>'+table(['Трафик','Политика','Повторы','Диапазон p95, с','Неуспех, %','Макс. lag, с'],comparison)
    distribution=[]
    cluster_b=lines(RESULTS/'B/cluster.jsonl')
    for name,rows in groups.items():
        if not name.startswith('B/'):continue
        expected=set()
        settings_path=RESULTS/name/'settings.json'
        if cluster_b and settings_path.exists():
            epoch=json.loads(settings_path.read_text(encoding='utf-8'))['epoch']
            nearest=min(cluster_b,key=lambda r:abs(r['wall']-epoch))
            expected={p['metadata']['name'] for p in nearest.get('pods',{}).get('items',[]) if p['metadata'].get('labels',{}).get('app')=='api' and not p['metadata'].get('deletionTimestamp') and any(c.get('type')=='Ready' and c.get('status')=='True' for c in p['status'].get('conditions',[]))}
        for pod in sorted({r.get('pod') for r in rows if r.get('pod')}|expected):
            subset=[r for r in rows if r.get('pod')==pod]; good=[r for r in subset if r['outcome']=='completed']
            distribution.append([name[2:],pod,len(subset),len(good),percentile([r.get('ttfc') for r in good],.95),percentile([r.get('queue_seconds') for r in good],.95),100*sum(bool(r.get('cache_hit')) for r in good)/len(good) if good else None])
    extra+=table(['Прогон','Pod','Запросов','Успешно','p95 TTFC, с','p95 очереди, с','Cache hit успешных, %'],distribution)
    hot_mapping=[]
    for name,rows in groups.items():
        if not name.startswith('B/hot-api-sticky-'):continue
        by_client={}
        for row in rows:
            by_client.setdefault(row['client'],Counter())[row.get('pod')]+=1
        for client,counts in sorted(by_client.items()):hot_mapping.append([name[2:],client,dict(counts)])
    if hot_mapping:
        extra+='<h3>Раскладка IP в горячих ClientIP-прогонах</h3>'+table(['Прогон','Клиент','Pod: число запросов'],hot_mapping)
        extra+='<p>80% задаётся на входе через client-0, а не как гарантированная доля запросов конкретного Pod. Если к той же реплике привязались и другие IP, её итоговая доля превышает 80%; это проверяется по трассе, а не предполагается заранее.</p>'
    if summaries['hot','api'] and summaries['hot','api-sticky']:
        ordinary=summaries['hot','api']; sticky=summaries['hot','api-sticky']
        better=sum(s['error_fraction'] for s in ordinary)<=sum(s['error_fraction'] for s in sticky)
        extra+='<p><b>Выбор по данным:</b> '+('обычный Service выбран как исправление постоянной ClientIP-привязки; по трём горячим прогонам суммарная доля неуспеха не выше, чем у ClientIP.' if better else 'обычный Service не подтвердил преимущество по доле неуспеха; результаты требуют дополнительной калибровки, устойчивое улучшение не заявляется.')+' Он не учитывает локальность кеша: запрос может вызвать miss на другой реплике. Переход к cache-aware маршрутизации требует отдельного измерения на настоящем engine.</p>'
    if 'A/rollout-A-B' in groups:
        rollout=summarize(groups['A/rollout-A-B'])
        text='<p><b>Цена штатного rollout:</b> '+str(rollout['completed'])+' из '+str(rollout['planned'])+' запросов завершились, p95 TTFC успешных = '+f"{rollout['ttfc_p95']:.3f}"+' с. Длинный поток занимает один вычислительный слот и увеличивает очередь. Graceful shutdown предотвращает потерю ответа, но не гарантирует низкую задержку; тайм-аут очереди 65 с подходит именно этому опыту и требует отдельной политики допуска при коротких дедлайнах.</p>'
        report=report.replace('<h2>B. Привязка, кеш и горячая реплика</h2>',text+'<h2>B. Привязка, кеш и горячая реплика</h2>')
    control=groups.get('controls/uniform-sticky-balanced',[])
    if control:
        cs=summarize(control)
        extra+='<h3>Контрольный случай без перекоса</h3><p>Отдельный условный контроль ClientIP выполнен с намеренно выбранной раскладкой: два клиентских IP на каждый Pod. Для этого использованы временные Service с теми же настройками ClientIP; все попытки выбора сохранены в results/controls/mapping-selection.json. Пробы /state не наполняют префиксный кеш. Взято то же расписание равномерной нагрузки 6 запросов/с на 120 с, что в основном сравнении. Это дополнительный контроль, а не замена трёх независимых повторов.</p>'
        extra+=table(['Условный контроль','Значение'],[['Распределение',cs['by_pod']],['Успешно / всего',str(cs['completed'])+' / '+str(cs['planned'])],['p95 TTFC, с',cs['ttfc_p95']],['Доля неуспеха',cs['error_fraction']]])
        extra+='<p>Отсутствие перегруза объясняется трассой: каждый IP закреплён, но суммарная интенсивность на каждом Pod равна 3 запросам/с и укладывается в ёмкость имитатора. Это не доказательство общей сбалансированности ClientIP: при раскладке 3+1 и при горячем клиенте результат меняется.</p>'
    report=report.replace('<h2>C. HPA и алерты</h2>',extra+'<h2>C. HPA и алерты</h2>')

    timing=[]
    up_path=RESULTS/'C/scale-up.json'; down_path=RESULTS/'C/scale-down.json'
    if up_path.exists():
        up=json.loads(up_path.read_text(encoding='utf-8'))
        timing.append(['3 Ready',up.get('error','получено')])
        settings_path=RESULTS/'C/scale-out/settings.json'
        if settings_path.exists() and 'wall' in up:
            epoch=json.loads(settings_path.read_text(encoding='utf-8'))['epoch']
            timing.append(['3 Ready после начала подачи, с',up['wall']-epoch])
            seen={}
            for record in lines(RESULTS/'C/cluster.jsonl'):
                for pod in record.get('pods',{}).get('items',[]):
                    if pod['metadata'].get('labels',{}).get('app')!='api':continue
                    created=datetime.fromisoformat(pod['metadata']['creationTimestamp'].replace('Z','+00:00')).timestamp()
                    if epoch <= created <= up['wall']:
                        conditions=[c for c in pod['status'].get('conditions',[]) if c['type']=='Ready' and c['status']=='True']
                        if conditions:
                            ready_at=datetime.fromisoformat(conditions[0]['lastTransitionTime'].replace('Z','+00:00')).timestamp()
                            seen[pod['metadata']['name']]=(created-epoch,ready_at-epoch)
            for pod,(created,ready_at) in seen.items():
                timing.extend([[pod+' создание, с от начала подачи',created],[pod+' Ready, с от начала подачи',ready_at]])
    if down_path.exists():
        down=json.loads(down_path.read_text(encoding='utf-8'))
        timing.append(['Возврат к 2 Ready после окончания нагрузки, с',down.get('observed_wait')])
        timing.append(['Scale-down',down.get('result',{}).get('error','получено')])
    cscale=groups.get('C/scale-out',[])
    if cscale:
        scale=summarize(cscale)
        timing.extend([['Стресс HPA: запланировано / успешно',str(scale['planned'])+' / '+str(scale['completed'])],['Стресс HPA: доля неуспеха',scale['error_fraction']]])
    chot=groups.get('C/sticky-hot-after-scale',[])
    if chot:
        cstart=json.loads((RESULTS/'C/sticky-hot-after-scale/settings.json').read_text(encoding='utf-8'))['epoch']
        cend=max(r['finished_wall'] for r in chot)
        active={p['metadata']['name'] for rec in lines(RESULTS/'C/cluster.jsonl') if cstart<=rec['wall']<=cend for p in rec.get('pods',{}).get('items',[]) if p['metadata'].get('labels',{}).get('app')=='api' and not p['metadata'].get('deletionTimestamp') and any(c.get('type')=='Ready' and c.get('status')=='True' for c in p['status'].get('conditions',[]))}
        counts=Counter(r.get('pod') for r in chot)
        timing.append(['Горячий ClientIP: получено по всем Ready Pod',dict((pod,counts[pod]) for pod in sorted(active))])
    rec_path=RESULTS/'B/hot-api-1/reconciliation.json'
    rec=json.loads(rec_path.read_text(encoding='utf-8')) if rec_path.exists() else {}
    reconcile='<h3>Сверка client / Prometheus</h3>'
    if rec:
        def value(key):
            result=rec.get(key,{}).get('data',{}).get('result',[])
            return float(result[0]['value'][1]) if result else 'нет данных'
        reconcile+=table(['Показатель','Значение'],[['Клиент: completed',rec['client_completed']],['Клиент: p95 TTFC, с',rec['client_p95']],['Histogram: p95, с',value('prometheus_p95')],['Histogram: наблюдений (оценка increase)',value('prometheus_observations')],['Дельта счётчика для неизменных Pod без экстраполяции',rec.get('counter_endpoint_delta')],['Совпавшие серверные terminal-записи',rec.get('matched_server_terminal_count')],['Точный серверный p95 по тем же request ID, с',rec.get('matched_server_exact_p95')],['Полное совпадение множества (Pod, request ID)',rec.get('same_completed_request_keys')]])
        reconcile+='<pre>'+html.escape(json.dumps(rec['promql'],ensure_ascii=False,indent=2))+'</pre><p>Сверка выполнена за один период и семейство completed. Сеть, интерполяция buckets и экстраполяция increase на границах scrape дают погрешность. Набор завершённых ответов дополнительно сверяется по (Pod, request ID) и terminal-записям. Дельта конечных значений счётчика допустима здесь, поскольку выбранные Pod не перезапускались в этом прогоне; она не заменяет reset-aware increase в общем случае. Равенство приближённых перцентилей не заявляется; сырые buckets сохранены в reconciliation.json.</p>'
    else:reconcile+='<p class="missing">Сверка ещё не получена.</p>'
    report=report.replace('<h2>Методика, PromQL и ограничения</h2>',table(['Масштабирование','Результат'],timing)+'<p>Вычислительный стресс HPA намеренно превышает пропускную способность при максимуме 3 реплики. Он доказывает реакцию контроллера, а не выполнение SLO без отказов. Горячий ClientIP выполняется после возврата к минимуму с продолжающим работать HPA: новая реплика не получает автоматически уже закреплённые IP. Алерт-стимул затем выполняется с фиксированными двумя репликами.</p>'+reconcile+'<h2>Методика, PromQL и ограничения</h2>')

    source='https://cloud.google.com/blog/products/containers-kubernetes/how-gke-inference-gateway-improved-latency-for-vertex-ai'
    case='<p>Кейс лекции: <b>Google Cloud, Vertex AI / GKE Inference Gateway, 08:20</b>. Таймкод выбран по сообщённому автором интервалу показа слайда 08:14–08:35. В первичной публикации описана маршрутизация с совместным учётом префиксного кеша и очереди. Увеличение веса очереди позволяет обходить горячую реплику даже при cache hit. Это согласуется с выбором свободной B, когда её пересчёт 0,8 с дешевле ожидания A в 3 с. Наш CPU-стенд не воспроизводит сам GKE Inference Gateway или настоящий KV-cache; количественные показатели Google и наши TTFC напрямую не сравниваются.</p><p>Первичный источник: <a href="'+source+'">Google Cloud — How we cut Vertex AI latency by 35% with GKE Inference Gateway</a>.</p>'
    report=re.sub(r'<p>Первичный источник для сопоставления:.*?</p>',lambda m:case,report,flags=re.S)
    report=re.sub(r'<p>Источник основы:.*?</p>','<p>Связь с собственным ДЗ 8–10 и происхождение использованной обвязки раскрыты в <a href="PROVENANCE.md">PROVENANCE.md</a>. Чужие результаты в этот отчёт не переносились.</p>',report,flags=re.S)
    review=report.split('<h2>Ревью предложения закрепить диалог за Pod</h2>',1)[-1].split('<h2>',1)[0]
    plain=html.unescape(re.sub('<[^>]+>','',review.replace('</p>','\n\n')))
    (ROOT/'REVIEW.md').write_text('# Ревью маршрутизации\n\n'+plain+'\n\n'+source+'\n',encoding='utf-8')
    publication_path=ROOT/'publication.json'
    publication=json.loads(publication_path.read_text(encoding='utf-8')) if publication_path.exists() else {}
    final='<h2>Воспроизведение и состав сдачи</h2><p>Команды запуска и удаления только собственного кластера — в README.md. Сырые ответы — results/requests.csv и client-*.jsonl; Kubernetes/Ready/EndpointSlice/HPA — cluster.jsonl; метрики и ALERTS — prometheus.jsonl; версии и размеры — evidence/. Срок хранения Prometheus ограничен 6 часами/384 МБ (том 512 MiB), Grafana — 128 MiB.</p>'
    if publication.get('repository'):
        final+='<p>Репозиторий: <a href="'+html.escape(publication['repository'])+'">'+html.escape(publication['repository'])+'</a>. Коммит с кодом: '+html.escape(publication.get('commit','добавить после публикации'))+'.</p>'
    else:final+='<p class="missing">Комплект подготовлен локально. Личный репозиторий и опубликованный коммит пока не указаны. Их нужно добавить перед сдачей; публикация в GitHub не выполнялась.</p>'
    size_path=ROOT/'evidence/stand-size.json'
    if size_path.exists():
        sizes=json.loads(size_path.read_text(encoding='utf-8'))
        names={'node_rootfs_bytes':'Rootfs узла (включая изменяемый слой)','node_writable_bytes':'В том числе изменяемый слой узла','node_var_volume_bytes':'Том /var учебного узла','host_application_image_bytes':'Образ API на хосте','logical_total_bytes':'Логическая сумма (RW отдельно не прибавляется)'}
        final+='<h3>Измеренный размер стенда</h3>'+table(['Составляющая','GiB'],[[names.get(key,key),value/1024**3] for key,value in sizes.items() if key.endswith('_bytes') and isinstance(value,(int,float))])
        final+='<p>Логическая сумма включает rootfs учебного узла, его том /var и образ приложения на хосте. Общие слои не вычтены; build cache и локальные инструменты учитываются отдельно в полной инвентаризации. Размер общего Docker VHDX не равен размеру этой работы, а удаление кластера не гарантирует немедленного сжатия VHDX.</p>'
    final+='<h3>Технические источники</h3><p><a href="https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/">Kubernetes: startup/readiness/liveness</a>; <a href="https://kubernetes.io/docs/concepts/services-networking/service/#session-affinity">Kubernetes: ClientIP</a>; <a href="https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/">Kubernetes: HPA</a>; <a href="https://prometheus.io/docs/practices/histograms/">Prometheus: Histogram</a>; <a href="https://kubernetes.io/blog/2025/02/28/nftables-kube-proxy/">Kubernetes: nftables kube-proxy</a>.</p>'
    final+='<p class="small">Сформировано из собственных данных: '+datetime.now(timezone(timedelta(hours=3))).isoformat(timespec='seconds')+'.</p>'
    report=report.replace('</html>',final+'</html>')
    (ROOT/'report.html').write_text(report,encoding='utf-8')
    status=dict(requests=len(all_rows),checks=len(checks),passed=passed,figures=len(pngs),reconciliation=bool(rec),complete_evidence=len(checks)>=16 and passed==len(checks) and len(pngs)==4 and rec.get('same_completed_request_keys') is True and sum(name.startswith('B/') for name in groups)==12,publication=publication)
    (ROOT/'submission-status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(status,ensure_ascii=False))


if __name__=='__main__':main()
