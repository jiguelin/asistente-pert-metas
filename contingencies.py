"""Calendar rules for one optional replacement, with mutually exclusive routes."""
import calendar
import json
import unicodedata
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal


def capacity_schedule(f):
    if 'minutos_semana' not in f:return None
    minutes=json.loads(f['minutos_semana'])
    if len(minutes)!=7 or any(not isinstance(x,(int,float)) or x<0 for x in minutes):
        raise ValueError('Disponibilidad semanal inválida')
    start,end=date.fromisoformat(f['inicio']),date.fromisoformat(f['fin'])
    result={}
    exceptions=json.loads(f.get('excepciones_tiempo','{}'))
    while start<=end:
        value=minutes[start.weekday()]
        if f.get('cobro_fin_mes')=='true' and start.day==calendar.monthrange(start.year,start.month)[1]:
            value=max(value,float(f.get('minutos_cobro','0')))
        if start.isoformat() in exceptions:value=exceptions[start.isoformat()]
        if not isinstance(value,(int,float)) or value<0:raise ValueError('Excepción de tiempo inválida')
        result[start.isoformat()]=value
        start+=timedelta(days=1)
    return result


def business_day(day,count):
    for _ in range(count):
        day+=timedelta(days=1)
        while day.weekday()>4:day+=timedelta(days=1)
    return day


def replacement_errors(plan,group):
    """Recheck the optional route manifest, including approved courier rules."""
    byid={n['id']:n for n in plan['notas']}
    ident=group['id'];task=byid[ident]
    if task.get('workflow')!='reposicion':return []
    errors=[];routes=group['rutas'];trigger=task['activador']
    expected_activations={(trigger,s['fecha']) for s in plan['sesiones'] if s['id']==trigger}
    activations=[(r['activacion']['id'],r['activacion']['fecha']) for r in routes]
    if not expected_activations or set(activations)!=expected_activations or len(activations)!=len(set(activations)):
        errors.append('Las rutas de reposición deben cubrir cada comprobación de entrega una sola vez')
    deadline=date.fromisoformat(plan['fin'])
    for origin,target,_ in plan['conexiones']:
        if origin==ident and target in byid and byid[target]['tipo'] in ['M','MP']:
            deadline=min(deadline,date.fromisoformat(byid[target]['fin']))
    calendar_rules=group.get('calendario')
    for route in routes:
        order,arrival,check,send,delivery,confirm=(date.fromisoformat(route[field]) for field in
            ['pedido','llegada_reemplazo','revision_reemplazo','reenvio','entrega_reemplazo','confirmacion'])
        activation=date.fromisoformat(route['activacion']['fecha'])
        if not activation<=order<arrival<=check<=send<delivery<=confirm<=deadline:
            errors.append('Fechas de reposición fuera de orden o del plazo de entrega')
        saturday=calendar_rules['recogida_sabados'] if calendar_rules else True
        if order.weekday()>4 or arrival.weekday()>4 or delivery.weekday()>4 or send.weekday()>(5 if saturday else 4):
            errors.append('La reposición incumple los días de pedido, recogida o entrega')
        if calendar_rules and (arrival!=business_day(order,calendar_rules['reposicion_habiles']) or
                               delivery!=business_day(send,calendar_rules['entrega_habiles'])):
            errors.append('La reposición incumple los plazos hábiles del courier')
        approved=defaultdict(float);actual=defaultdict(float)
        for day,minutes in [(order,10),(check,5),(send,15),(confirm,10)]:
            approved[day.isoformat()]+=minutes
        for session in route['sesiones']:actual[session['fecha']]+=session['minutos']
        if dict(actual)!=dict(approved):
            errors.append('Cada ruta debe incluir los 40 minutos aprobados de pedido, revisión, reenvío y confirmación')
        dates=sorted(approved)
        required_edges=[[trigger,route['activacion']['fecha'],ident,dates[0]]]+[[ident,x,ident,y] for x,y in zip(dates,dates[1:])]
        if any(edge not in route.get('dependencias_evento',[]) for edge in required_edges):
            errors.append('Faltan dependencias de activación o de las etapas de reposición')
    return errors


def compile_replacement(plan,f):
    """Same approved 10+20+10 minutes; choose slots for each possible incident."""
    if f.get('tipo')!='empresa':return
    required=['entrega_habiles','entrega_lun_vie','recogida_sabados','reposicion_habiles']
    if not all(k in f for k in required) or f['entrega_lun_vie']!='true':return
    clean=lambda text: ''.join(c for c in unicodedata.normalize('NFKD',str(text).lower()) if not unicodedata.combining(c))
    candidates=[n for n in plan['notas'] if n['tipo']=='T' and (n.get('workflow')=='reposicion' or 'reposici' in clean(n.get('texto','')))]
    if not candidates:return
    if len(candidates)!=1:raise ValueError('La reposición debe estar consolidada en una sola tarea')
    task=candidates[0];ident=task['id'];byid={n['id']:n for n in plan['notas']}
    trigger=task.get('activador')
    if trigger not in byid:
        possible=[n['id'] for n in plan['notas'] if n['tipo']=='T' and 'entreg' in clean(n.get('texto','')+' '+n.get('detalle','')) and ('confirm' in clean(n.get('texto','')) or 'inciden' in clean(n.get('texto','')))]
        if len(possible)!=1:raise ValueError('Indica el ID de la tarea que confirma entregas y detecta daños')
        trigger=possible[0]
    activations=sorted({s['fecha'] for s in plan['sesiones'] if s['id']==trigger})
    if not activations:raise ValueError('Faltan comprobaciones de entrega que activen la reposición')
    # Normal work remains unchanged. Alternatives are validated separately.
    plan['sesiones']=[s for s in plan['sesiones'] if s['id']!=ident]
    plan['dependencias']=[e for e in plan['dependencias'] if e!=[trigger,ident]]
    plan['dependencias_evento']=[e for e in plan.get('dependencias_evento',[]) if ident not in [e[0],e[2]]]
    plan['dependencias_sesion']=[e for e in plan.get('dependencias_sesion',[]) if ident not in e]
    base=defaultdict(float)
    for session in plan['sesiones']:base[session['fecha']]+=session['minutos']
    last=date.fromisoformat(plan['fin'])
    destinations={y for x,y,_ in plan['conexiones'] if x==ident}
    for target in destinations:
        if target in byid and byid[target]['tipo'] in ['M','MP']:
            last=min(last,date.fromisoformat(byid[target]['fin']))
    routes=[]
    for activation in activations:
        load=defaultdict(float,base);sessions=[]
        def reserve(earliest,minutes,allowed):
            day=earliest
            while day<=last:
                key=day.isoformat()
                if allowed(day) and load[key]+minutes<=plan['capacidad'].get(key,0):
                    load[key]+=minutes;sessions.append({'id':ident,'fecha':key,'minutos':minutes})
                    return day
                day+=timedelta(days=1)
            raise ValueError('No hay tiempo para la reposición activada el '+activation)
        order=reserve(date.fromisoformat(activation),10,lambda d:d.weekday()<5)
        arrival=business_day(order,int(Decimal(f['reposicion_habiles'])))
        check=reserve(arrival,5,lambda d:True)
        send=reserve(check,15,lambda d:d.weekday()<5 or (d.weekday()==5 and f['recogida_sabados']=='true'))
        delivery=business_day(send,int(Decimal(f['entrega_habiles'])))
        confirm=reserve(delivery,10,lambda d:True)
        merged=defaultdict(float)
        for s in sessions:merged[s['fecha']]+=s['minutos']
        dates=sorted(merged)
        edges=[[trigger,activation,ident,dates[0]]]+[[ident,x,ident,y] for x,y in zip(dates,dates[1:])]
        routes.append({'activacion':{'id':trigger,'fecha':activation},'pedido':order.isoformat(),
                       'llegada_reemplazo':arrival.isoformat(),'revision_reemplazo':check.isoformat(),
                       'reenvio':send.isoformat(),'entrega_reemplazo':delivery.isoformat(),
                       'confirmacion':confirm.isoformat(),
                       'sesiones':[{'id':ident,'fecha':d,'minutos':merged[d]} for d in dates],
                       'dependencias_evento':edges})
    task.update(condicional=True,workflow='reposicion',activador=trigger,
                inicio=min(r['pedido'] for r in routes),fin=max(r['confirmacion'] for r in routes),
                detalle='Solo si una caja llega dañada: 10 min pedir; 5 min revisar el reemplazo; 15 min reempacar con empaque nuevo y reenviar; 10 min confirmar entrega. Usa una sola ruta de la leyenda.',
                evidencia='Entrega del reemplazo comprobada si hubo daño; registro de entregas sin daños si no se activó.',
                frecuencia='Como máximo una reposición; no se ejecuta si no hay daño.')
    plan['contingencias']=[{'id':ident,'condicion':'Si una caja llega dañada','max_activaciones':1,'rutas':routes,
                           'calendario':{'reposicion_habiles':int(Decimal(f['reposicion_habiles'])),
                                         'entrega_habiles':int(Decimal(f['entrega_habiles'])),
                                         'recogida_sabados':f['recogida_sabados']=='true'}}]
    plan['conexiones']=[e for e in plan['conexiones'] if e[:2]!=[trigger,ident]]+[[trigger,ident,'si hay daño']]
