"""Verificador interno PERT físico, v4. Python estándar, sin red ni archivos.

Uso: exec(open(ruta_del_archivo).read()); resultado = verificar(plan)
No sustituye la revisión semántica de meta, hitos, datos y dependencias.
Todos los minutos, reservas y evidencias proceden del plan completo.
Nunca omitir trabajo para obtener un resultado favorable.

ESQUEMA plan:
inicio, fin: ISO YYYY-MM-DD.
periodos: [{inicio,fin}]; cada fecha exactamente una vez.
notas: [{id,tipo,texto,inicio,fin,evidencia}]; tipo M,T,H,O,A,MP.
  MP tiene fecha fin; T tiene rango completo; M tiene evidencia observable.
  O/A disponibles desde inicio; H desde práctica inicial.
sesiones: [{id,fecha,minutos}]; una entrada por ejecución de cada T.
  Expandir recurrencias con sesiones_recurrentes. Una T física, muchas sesiones.
capacidad: {fecha:minutos}; todos los días usados, incluidos excepcionales.
limite_semanal: minutos o None, semana ISO lunes-domingo.
dependencias: [[id_previo,id_siguiente]]; solo precedencias fin→inicio.
  Continuidades y contribuciones recurrentes a hitos van en conexiones, no aquí.
dependencias_sesion: [[T_previa,T_siguiente]]; orden repetido en cada fecha de la sucesora.
  Ambas tareas tienen sesión ese día; dibujar flecha rotulada «cada sesión».
  No convertir este orden en fin global→inicio global ni omitirlo.
dependencias_evento: [[T_previa,fecha_previa,T_siguiente,fecha_siguiente]];
  Para relaciones por lote o contingencias en días distintos: ambas ejecuciones existen y la previa no es posterior.
conexiones: [[origen,destino,tipo]]; tipo apoyo/riesgo/contribucion/continuidad.
finanzas: bool; caja: [{fecha,saldo,reserva,libre}].
  reserva = obligaciones hasta próximo ingreso, no un ahorro disponible.
materiales: {papel:[ancho,alto],nota:[ancho,alto],meta:[ancho,alto],pared:ancho}.
  Medidas en cm, confirmadas por alumno; pared puede None si no hay restricción.
pendientes: lista de restricciones esenciales sin resolver.

La salida incluye coordenadas de esquina superior izquierda por nota;
filas: 1 resultados, 2 tareas, 3 habilidades, 4 obstáculos, 5 apoyos.
La zona MP nunca es periodo. Leyendas fuera del papel; rótulos de fila por icono.
La función busca la menor cantidad de hojas con 1–3 periodos cada una,
ancho proporcional uniforme dentro de la hoja y hasta 70% de plazas por fila.
Si no cabe con esta plantilla, devuelve bloqueo; no elimina notas.
"""
from datetime import date, timedelta
from collections import Counter, defaultdict
from math import floor

def _d(s):
    return date.fromisoformat(s)

def sesiones_recurrentes(id, inicio, fin, dias, minutos):
    """dias: lunes=0 ... domingo=6; minutos: número o dict weekday→minutos."""
    a, b = _d(inicio), _d(fin)
    out = []
    while a <= b:
        if a.weekday() in dias:
            m = minutos if isinstance(minutos, (int, float)) else minutos[a.weekday()]
            out.append(dict(id=id, fecha=a.isoformat(), minutos=m))
        a += timedelta(days=1)
    return out

def verificar(p):
    errors = []
    try:
        a, b = _d(p['inicio']), _d(p['fin'])
        assert a <= b
        periods = [(_d(x['inicio']), _d(x['fin'])) for x in p['periodos']]
        assert periods and periods[0][0] == a and periods[-1][1] == b
        assert all(x <= y for x, y in periods)
        assert all(periods[i][1] + timedelta(days=1) == periods[i+1][0] for i in range(len(periods)-1))
    except (ValueError, KeyError, AssertionError):
        return {'ok': False, 'errores': ['Fechas o cobertura de periodos inválidas']}
    notes = p['notas']
    ids = [n['id'] for n in notes]
    if len(set(ids)) != len(ids): errors.append('IDs duplicados')
    byid = {n['id']: n for n in notes}
    if sum(n['tipo'] == 'MP' for n in notes) != 1: errors.append('Debe existir exactamente una MP')
    for n in notes:
        if n['tipo'] not in ('M','T','H','O','A','MP'): errors.append('Tipo inválido '+n['id'])
        try:
            if not a <= _d(n['inicio']) <= _d(n['fin']) <= b: errors.append('Rango fuera de plan '+n['id'])
        except (ValueError, KeyError): errors.append('Fecha inválida '+n['id'])
        if n['tipo'] in ('M','H','MP') and not n.get('evidencia'): errors.append('Falta evidencia '+n['id'])
    daily, weekly, totals = defaultdict(float), defaultdict(float), defaultdict(float)
    for s in p['sesiones']:
        n = byid.get(s['id'])
        if not n or n['tipo'] != 'T': errors.append('Sesión sin tarea '+s['id']); continue
        d = _d(s['fecha']); minutes = s['minutos']
        if minutes <= 0: errors.append('Esfuerzo no positivo '+s['id'])
        if not _d(n['inicio']) <= d <= _d(n['fin']): errors.append('Sesión fuera de rango '+s['id'])
        daily[s['fecha']] += minutes; weekly[d.isocalendar()[:2]] += minutes; totals[s['id']] += minutes
    for n in notes:
        if n['tipo'] == 'T' and totals[n['id']] <= 0: errors.append('Tarea sin carga programada '+n['id'])
    for d, m in daily.items():
        cap = p['capacidad'].get(d)
        if cap is None or m > cap: errors.append(f'Carga diaria {d}: {m} min; disponible {cap}')
    limit = p.get('limite_semanal')
    if limit is not None:
        for w, m in weekly.items():
            if m > limit: errors.append(f'Carga semanal {w}: {m} > {limit}')
    for x, y in p['dependencias']:
        if x not in byid or y not in byid: errors.append('Dependencia con ID inexistente'); continue
        if _d(byid[x]['fin']) > _d(byid[y]['inicio']): errors.append(f'Precedencia imposible {x}→{y}')
    session_dates = defaultdict(set)
    for s in p['sesiones']:
        session_dates[s['id']].add(s['fecha'])
    session_edges = p.get('dependencias_sesion', [])
    for x, y in session_edges:
        if x not in byid or y not in byid or byid[x]['tipo'] != 'T' or byid[y]['tipo'] != 'T':
            errors.append('Dependencia por sesión requiere dos tareas existentes'); continue
        missing = session_dates[y] - session_dates[x]
        if missing: errors.append(f'Falta sesión previa {x}→{y}: {sorted(missing)}')
    event_edges = p.get('dependencias_evento', [])
    for x, dx, y, dy in event_edges:
        if x not in byid or y not in byid or byid[x]['tipo'] != 'T' or byid[y]['tipo'] != 'T':
            errors.append('Dependencia por evento requiere dos tareas existentes'); continue
        if dx not in session_dates[x] or dy not in session_dates[y]:
            errors.append(f'Dependencia por evento sin ejecución {x}/{dx}→{y}/{dy}')
        if _d(dx) > _d(dy): errors.append(f'Evento previo posterior {x}/{dx}→{y}/{dy}')
    graph = defaultdict(list)
    for x, y in p['dependencias'] + session_edges:
        graph[x].append(y)
    active, done = set(), set()
    def cyclic(x):
        if x in active: return True
        if x in done: return False
        active.add(x)
        if any(cyclic(y) for y in graph.get(x, [])): return True
        active.remove(x); done.add(x)
        return False
    if any(cyclic(x) for x in list(graph)): errors.append('Ciclo en dependencias')
    graph = defaultdict(list)
    for x, dx, y, dy in event_edges: graph[(x, dx)].append((y, dy))
    for x, y in session_edges:
        for dy in session_dates[y]: graph[(x, dy)].append((y, dy))
    active.clear(); done.clear()
    if any(cyclic(x) for x in list(graph)): errors.append('Ciclo entre eventos/sesiones')
    for x,y,t in p.get('conexiones',[]):
        if x not in byid or y not in byid: errors.append('Conexión con ID inexistente')
    if p.get('finanzas') and not p.get('caja'): errors.append('Falta flujo y reservas')
    for c in p.get('caja',[]):
        if abs(c['saldo']-c['reserva']-c['libre']) > .01: errors.append('Saldo libre incorrecto '+c['fecha'])
        if c['libre'] < 0: errors.append('Déficit de caja '+c['fecha'])
    errors.extend('Pendiente: '+x for x in p.get('pendientes',[]))
    W,H = p['materiales']['papel']; w,h = p['materiales']['nota']; mw,mh = p['materiales']['meta']
    gap,margin,top,bottom = 1.5,3,9,4
    zone = max(18,mw+3); rowh = (H-top-bottom)/5
    counts = [Counter() for _ in periods]; bucket = {}
    lane = {'M':0,'T':1,'H':2,'O':3,'A':4}
    for n in notes:
        if n['tipo'] == 'MP': continue
        d = _d(n['fin'] if n['tipo']=='M' else n['inicio'])
        matches = [i for i,(x,y) in enumerate(periods) if x<=d<=y]
        if len(matches)!=1: errors.append('Sin periodo '+n['id']); continue
        i=matches[0]; bucket[n['id']]=i; counts[i][n['tipo']]+=1
    def fit(first,k):
        final = first+k==len(periods)
        available = W-2*margin-(zone if final else 0)
        cw=available/k; slots=floor((cw-3)/(w+gap)); allowed=floor(.70*slots)
        return h+gap<=rowh and (not final or mh<=H-top-bottom) and allowed>0 and all(max(counts[i].values(),default=0)<=allowed for i in range(first,first+k))
    def solve(first):
        if first==len(periods): return []
        options=[]
        for k in range(1,min(3,len(periods)-first)+1):
            if fit(first,k):
                rest=solve(first+k)
                if rest is not None: options.append([k]+rest)
        return min(options,key=len) if options else None
    groups=solve(0); places=[]; density=[]
    if groups is None: errors.append('No cabe: ampliar papel/redistribuir periodos reales; conservar notas')
    else:
        wall=p['materiales'].get('pared')
        if wall is not None and len(groups)*W>wall: errors.append('Ancho de pared insuficiente')
        first=0
        for sheet,k in enumerate(groups,1):
            cw=(W-2*margin-(zone if sheet==len(groups) else 0))/k
            slots=floor((cw-3)/(w+gap)); rank=Counter()
            for n in notes:
                i=bucket.get(n['id'])
                if i is None or not first<=i<first+k: continue
                col=i-first; r=lane[n['tipo']]; ix=rank[(col,r)];rank[(col,r)]+=1
                places.append(dict(id=n['id'],papel=sheet,columna=col+1,fila=r+1,x=round(margin+col*cw+1.5+ix*(w+gap),2),y=round(top+r*rowh,2)))
            for j in range(k): density.append(dict(papel=sheet,columna=j+1,periodo=first+j+1,ancho=round(cw,2),conteo=dict(counts[first+j]),capacidad_fila=slots,maximo_usado=max(counts[first+j].values(),default=0)))
            first+=k
        for n in notes:
            if n['tipo']=='MP': places.append(dict(id=n['id'],papel=len(groups),columna='zona final',fila=1,x=W-margin-zone+1.5,y=top))
    return dict(ok=not errors,errores=errors,dependencias=p['dependencias'],dependencias_sesion=session_edges,dependencias_evento=event_edges,dias_inclusivos=(b-a).days+1,minutos_totales=sum(daily.values()),minutos_por_tarea=dict(totals),cargas_por_dia=dict(sorted(daily.items())),papelografos=len(groups) if groups else None,periodos_por_papel=groups,densidad=density,posiciones=places)
