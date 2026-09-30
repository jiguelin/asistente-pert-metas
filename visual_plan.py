"""Visual roadmap validation and relative layout. No session scheduling."""
from datetime import date, timedelta
from collections import Counter
from copy import deepcopy
import calendar

MONTHS='enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
LANES={'M':'Mini metas','T':'Tareas principales','H':'Habilidades','O':'Obstáculos','A':'Apoyos'}

def periods(start,end):
    a,b=date.fromisoformat(start),date.fromisoformat(end)
    if b<a:raise ValueError('La fecha límite debe ser posterior al inicio.')
    out=[];d=a;days=(b-a).days+1
    months=(b.year-a.year)*12+b.month-a.month+1
    step=1 if months<=6 else 2 if months<=9 else 3 if months<=18 else max(4,(months+5)//6)
    while d<=b:
        if days<=42:
            last=min(b,d+timedelta(days=6));label=f'{d:%d/%m} - {last:%d/%m/%Y}'
        else:
            y,m=divmod(d.year*12+d.month-1+step-1,12);m+=1
            last=min(b,date(y,m,calendar.monthrange(y,m)[1]))
            label=f'{MONTHS[d.month-1]} {d.year}' if (d.year,d.month)==(last.year,last.month) else f'{MONTHS[d.month-1]} {d.year} - {MONTHS[last.month-1]} {last.year}'
        out.append({'inicio':d.isoformat(),'fin':last.isoformat(),'label':label})
        d=last+timedelta(days=1)
    return out

def audit_visual(plan):
    p=deepcopy(plan);a,b=date.fromisoformat(p['inicio']),date.fromisoformat(p['fin'])
    ps=periods(p['inicio'],p['fin']); notes=p['notas']; ids=[n['id'] for n in notes]
    if not notes or len(set(ids))!=len(ids):raise ValueError('Notas vacías o IDs repetidos.')
    byid={n['id']:n for n in notes}
    if sum(n['tipo']=='MP' for n in notes)!=1:raise ValueError('Se requiere una Meta Principal.')
    if not any(n['tipo']=='M' for n in notes):raise ValueError('Faltan mini metas.')
    for n in notes:
        if n['tipo'] not in [*LANES,'MP']:raise ValueError('Tipo de nota inválido.')
        if not n['texto'].strip() or len(n['texto'].split())>7:raise ValueError('Usa etiquetas cortas en los post-it.')
        if not a<=date.fromisoformat(n['fecha'])<=b:raise ValueError('Nota fuera del plazo.')
        if n['tipo']=='MP' and n['fecha']!=p['fin']:raise ValueError('La MP va en la fecha final.')
        if n['tipo'] in ('M','MP') and not n['evidencia'].strip():raise ValueError('Resultado sin comprobación.')
        if n['tipo']=='T':
            if not n['para'] or any(x not in byid or byid[x]['tipo'] not in ('M','MP') for x in n['para']):raise ValueError('Tarea sin resultado asociado.')
    for target in [n['id'] for n in notes if n['tipo'] in ('M','MP')]:
        if sum(n['tipo']=='T' and target in n['para'] for n in notes)>3:raise ValueError('Máximo tres tareas principales por resultado.')
    texts=[n['texto'].strip().casefold() for n in notes if n['tipo']=='T']
    if len(texts)!=len(set(texts)):raise ValueError('Tarea duplicada.')
    graph={k:[] for k in ids}
    for edge in p['conexiones']:
        x,y,t=edge['de'],edge['a'],edge['tipo']
        if x not in byid or y not in byid or x==y:raise ValueError('Conexión inválida.')
        if t=='antes':
            if byid[x]['fecha']>byid[y]['fecha']:raise ValueError('Dependencia con fecha inversa.')
            graph[x].append(y)
        elif t not in ('contribuye','apoyo','riesgo'):raise ValueError('Relación desconocida.')
    done=set();active=set()
    def visit(x):
        if x in active:raise ValueError('Dependencias circulares.')
        if x in done:return
        active.add(x)
        for y in graph[x]:visit(y)
        active.remove(x);done.add(x)
    for x in ids:visit(x)
    counts=[Counter() for _ in ps]
    for n in notes:
        if n['tipo']=='MP':continue
        i=next(i for i,q in enumerate(ps) if q['inicio']<=n['fecha']<=q['fin'])
        n['periodo']=i;counts[i][n['tipo']]+=1
    # More crowded real periods receive more paper width, never fake columns.
    sheets=[];i=0
    while i<len(ps):
        group=[]
        while i<len(ps) and len(group)<3:
            dense=max(counts[i].values(),default=0)>3
            if dense and group:break
            group.append(i);i+=1
            if dense:break
        sheets.append(group)
    if any(max(c.values(),default=0)>6 for c in counts):raise ValueError('Demasiadas notas juntas: agrupa equivalentes sin perder su detalle.')
    for s,group in enumerate(sheets,1):
        for n in notes:
            if n['tipo']!='MP' and n['periodo'] in group:n['hoja']=s;n['columna']=group.index(n['periodo'])+1
    mp=next(n for n in notes if n['tipo']=='MP');mp['hoja']=len(sheets);mp['columna']='zona final'
    p['modo']='visual';p['periodos']=ps
    return {'plan':p,'hojas':sheets,'dias_inclusivos':(b-a).days+1,'notas_pequenas':len(notes)-1,'densidad':[dict(c) for c in counts]}


def proposal_text(p):
    lines=[f"**Meta Principal:** {p['meta']}",f"**Punto de partida:** {p['situacion']}",f"**Obstáculo principal:** {p['principal']}",f"**Cómo afrontarlo desde el inicio:** {p['estrategia']}",'','**Mini metas propuestas**']
    for n in p['notas']:
        if n['tipo']=='M':lines.append(f"- **{n['id']} · {n['texto']}** — {n['fecha']}. {n['detalle']} Comprobación: {n['evidencia']}")
    lines+=['','**Tareas principales propuestas**']
    tasks=[n for n in p['notas'] if n['tipo']=='T']
    for n in tasks:lines.append(f"- **{n['id']} · {n['texto']}** — {n['detalle']} Para: {', '.join(n['para'])}. Ubicación orientativa: {n['fecha']}.")
    if not tasks:lines.append('No hace falta añadir tareas al mapa: las mini metas ya orientan el siguiente paso.')
    lines+=['',f"**Orden y líneas paralelas:** {p['secuencia']}",'','Las fechas intermedias son propuestas. El detalle diario lo llevas en tu agenda.']
    return '\n'.join(lines)


def final_text(audit):
    p=audit['plan'];lines=[proposal_text(p),'','**Así armas tu mapa visual**',f"Del {p['inicio']} al {p['fin']}: {audit['dias_inclusivos']} días inclusivos. Usa {len(audit['hojas'])} papelógrafo(s) horizontales."]
    for i,group in enumerate(audit['hojas'],1):
        labels=' | '.join(p['periodos'][j]['label'] for j in group)
        lines.append(f"- Hoja {i}: {len(group)} columna(s): {labels}.")
    lines+=['Reserva una zona a la derecha de la última hoja para la Meta Principal, fuera de las columnas. No es un periodo adicional.',
    'Usa post-it pequeños (un cuarto del habitual), con el ID y la etiqueta corta. Para la Meta Principal, uno normal o una tarjeta donde quepa el texto completo.',
    'Coloca bandas para mini metas, tareas, habilidades, obstáculos y apoyos. El PDF indica dónde ubicar cada nota. Deja espacio entre notas para moverlas y dibujar las conexiones relevantes.',
    '**Cada semana:** comprueba avances, marca logros, mueve notas o ajusta fechas y añade obstáculos o apoyos que aparezcan. Desglosa tus acciones pequeñas en tu agenda.',
    'Descarga el PDF para conservar el mapa, todas las notas y su leyenda. La distribución es orientativa; adapta el espaciado al papel que uses.']
    return '\n\n'.join(lines)
