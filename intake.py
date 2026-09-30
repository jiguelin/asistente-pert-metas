"""Evidence-backed intake and calculations before the next teaching step."""
import calendar
import json
import unicodedata
from datetime import date, timedelta
from decimal import Decimal

KEYS = '''meta criterio inicio fin situacion obstaculos principal habilidades apoyos disponibilidad minutos_semana minutos_cobro excepciones_tiempo papel nota meta_nota pared papeles tipo saldo capital ingreso gasto cobro_fin_mes gastos_inicio_pagados reserva objetivo unidades precio costo empaque publicidad inventario_disponible otros_costos primer_envio_cliente reposicion reposicion_caja reposicion_empaque reposicion_envio entrega_habiles entrega_lun_vie recogida_sabados reposicion_habiles mini_aprobadas tareas_aprobadas'''.split()
SCHEMA = {"type":"object","properties":{
    "ambiguedad_esencial":{"type":["string","null"]},
    "meta_verificable":{"type":"boolean"},
    "meta_cambiada":{"type":"boolean"},
    "cambio_meta_cita":{"type":["string","null"]},
    "hechos":{"type":"array","items":{"type":"object","properties":{
        "campo":{"type":"string","enum":KEYS},"valor":{"type":"string"},
        "usuario":{"type":"integer"},"cita":{"type":"string"}},
        "required":["campo","valor","usuario","cita"],"additionalProperties":False}}
},"required":["ambiguedad_esencial","meta_verificable","meta_cambiada","cambio_meta_cita","hechos"],"additionalProperties":False}

PROMPT = '''Extrae datos para un PERT físico, sin redactar respuesta al alumno ni hacer planes.
Usa SOLO hechos declarados por el usuario o propuestas concretas que este aceptó.
Cada hecho lleva índice usuario (primer usuario=0) y cita literal CORTA, copiada exactamente, sin normalizar números ni añadir puntos suspensivos.
Con datos de saldo, ingresos y gastos, situacion ya está respondida: sintetízala.
Con inventario actual, interesados y ventas pagadas, situacion ya está respondida.
No conviertas su silencio o una solicitud de continuar en aceptación de fechas inventadas.
No inventes fechas, habilidades, apoyos, medidas ni cifras. Reutiliza todos los datos adelantados.
Fechas inicio/fin: ISO con año. Importes: número sin moneda ni separadores de miles.
papel/nota/meta_nota: JSON [ancho,alto] en cm. pared/papeles: número.
tipo: ahorro si la meta exige dinero libre; empresa si exige ganancia comercial; otro si no.
cobro_fin_mes/gastos_inicio_pagados: true o false. No asumas false cuando no se sabe.
saldo=dinero inicial libre en ahorro; capital=dinero disponible inicial de una empresa
(no llamarlo libre si no está separado de obligaciones). ingreso/gasto=mensuales; reserva=dinero final intocable;
minutos_semana: JSON [lunes,martes,miércoles,jueves,viernes,sábado,domingo] de MINUTOS
confirmados; días no disponibles=0. Solo si los días están declarados; no inventar reparto
de un total semanal. Integra datos repartidos entre respuestas: si primero declara
duraciones y después los días, conserva ambas cosas y devuelve minutos_semana.
Si declara un intervalo de duración (45 minutos a una hora; media hora a 45), usa
el extremo inferior expresado para capacidad conservadora: 45+30=75 minutos.
Esto no cambia sus horarios ni exige usar todo el bloque. «Todos los días» confirma
lunes a domingo. disponibilidad debe resumir días Y duraciones ya declarados,
nunca sustituir un horario completo por la última respuesta que solo aporta días.
minutos_cobro: minutos disponibles el día del cobro si explícitos.
excepciones_tiempo: objeto JSON fecha ISO:minutos, solo excepciones declaradas;
0 si no puede trabajar ese día. No inventar excepciones ni omitirlas si fueron aportadas.
objetivo=umbral libre; empresa: unidades,precio,costo unitario,empaque unitario,
publicidad total y costos de reposicion_caja/empaque/envio o reposicion total si explícito.
inventario_disponible=true solo si ya posee las unidades; otros_costos=0 solo si
declara que no hay otros costos/comisiones; primer_envio_cliente=true solo si
el cliente paga el primer envío. No asumir estas condiciones por silencio.
Si están declarados: entrega_habiles y reposicion_habiles son números de días;
entrega_lun_vie=true solo con entregas de lunes a viernes; recogida_sabados=true
solo si recoge sábados. False solo si se excluyen explícitamente; no inventar horarios.
Un gasto ya pagado en el mes inicial NO se vuelve a restar. Una reserva no elimina un costo.
Meta verificable: hay resultado observable, cantidad o evidencia suficiente. Distingue
criterios ESENCIALES de preferencias personales. Con un resultado observable, energía,
ánimo, entusiasmo, felicidad o confianza son valoraciones del alumno: consérvalas,
pero no exijas definirlas ni medirlas. «Caminar 5 km con buena energía» y «pesar 70 kg
con músculos y abdomen marcados y alta energía» permiten avanzar. Apariencia marcada
admite observación personal; al proponer hitos ofrece evidencia sencilla, sin imponer
porcentaje de grasa, pruebas clínicas ni fotografías obligatorias. No persigas sinónimos
«alta energía»→«pilas»→«entusiasmado»→«feliz». Tampoco impongas un límite de café.
Una cifra o fecha cualquiera NO hace verificable todo: «reporte profesional de 10 páginas»
todavía puede necesitar contenido y comprobación. «Sentirme con alta energía» como única
meta necesita UNA aclaración útil del logro, proponiendo una comprobación sencilla.
ambiguedad_esencial: solo el término o frase LITERAL del usuario que impide verificar,
sin explicación. Revisar también la última aclaración: «bien presentado» u «ordenado»
sin característica observable no resuelven «profesional».
Si la última aclaración introduce una nueva vaguedad ESENCIAL, señala una de ellas;
no confundas sensaciones, preferencias o respuestas a una pregunta innecesaria con
una nueva condición esencial. Una meta ya admitida no se reabre por nuevos sinónimos.
No acreditar definiciones vagas sugeridas por el asistente. No confundir preferencias
de estilo con criterios esenciales.
meta_cambiada=true SOLO si el ÚLTIMO usuario solicita cambiar un resultado o criterio
esencial, lo contradice o añade una condición indispensable que obliga a revisarlo.
cambio_meta_cita: cita literal corta de ese ÚLTIMO mensaje, o null si no hay cambio.
Actualizar peso actual, disponibilidad, apoyos, fechas o explicar sensaciones no cambia
el objetivo. Reescribir la meta al extraerla tampoco. Si ya se pasó a situación, obstáculos,
habilidades o apoyos, no retroceder a criterio por preferencias sin cambio esencial real.
criterio: conserva los requisitos reales sin añadir otros. habilidades son las necesarias
para superar el obstáculo, no convertir situación actual en una habilidad futura.
«Ningún obstáculo» / «ningún apoyo» son hechos válidos. No inferir principal de una lista.
mini_aprobadas=true solo si el usuario aceptó una propuesta con mini metas M1... en
resultados verificables, fechas y evidencia. tareas_aprobadas=true solo si aceptó el
cronograma con IDs, fechas, frecuencia y minutos; aceptar una lista sin esos datos NO basta.
Una aprobación de propuesta concreta puede acreditar sus valores: cita la aceptación,
pero nunca acredita algo que no figuraba en la propuesta. «Propón el cronograma» no lo aprueba.
Si cambia un criterio o la fecha, invalidar aprobaciones afectadas. Valores faltantes: omitir hecho.
Devuelve exclusivamente el JSON del esquema. contexto con mensajes A=asistente, U=usuario:
'''


def context(messages):
    users=[]; lines=[]
    for m in messages:
        if m['role']=='user':
            users.append(m['content']);label=f'U{len(users)-1}'
        else:label='A'
        lines.append(label+': '+m['content'])
    return users,'\n'.join(lines)


def normalize(payload, users, known_facts=None, accepted_goal=None):
    facts={k:v for k,v in (known_facts or {}).items()
           if k not in ['mini_aprobadas','tareas_aprobadas']}
    clean=lambda text: ' '.join(unicodedata.normalize('NFKC',text).split())
    for h in payload['hechos']:
        i=h['usuario'];q=h['cita']
        # Source text is authoritative; a mistaken message index must not
        # erase a fact when its literal quotation exists in the transcript.
        if q and any(clean(q) in clean(user) for user in users):
            facts[h['campo']]=h['valor']
    if 'situacion' not in facts and facts.get('tipo')=='ahorro' and all(k in facts for k in ['saldo','ingreso','gasto']):
        facts['situacion']=f"Saldo libre {facts['saldo']}; ingreso mensual {facts['ingreso']}; gasto mensual {facts['gasto']}."
    if facts.get('obstaculos','').strip().lower() in ['ninguno','ningún obstáculo','no tengo obstáculos']:
        facts.setdefault('principal','ninguno')
    # A verification decision belongs to this goal, not to each new turn's
    # wording. Reopen only on a changed requirement attributable to the latest
    # student message; an old quote or an extractor paraphrase is insufficient.
    quote=payload.get('cambio_meta_cita')
    changed=(payload.get('meta_cambiada') is True and isinstance(quote,str)
             and bool(quote.strip()) and bool(users)
             and clean(quote) in clean(users[-1]))
    result={**payload,'facts':facts,'meta_cambiada':changed}
    if changed:
        facts.pop('mini_aprobadas',None)
        facts.pop('tareas_aprobadas',None)
    elif isinstance(accepted_goal,dict) and accepted_goal.get('meta'):
        facts['meta']=accepted_goal['meta']
        if accepted_goal.get('criterio'):
            facts['criterio']=accepted_goal['criterio']
        result['meta_verificable']=True
        result['ambiguedad_esencial']=None
    result['goal_validation']=(
        {'meta':facts['meta'],'criterio':facts.get('criterio','')}
        if facts.get('meta') and result['meta_verificable'] is True
        and not result['ambiguedad_esencial'] else None)
    return result


def stage(snapshot):
    f=snapshot['facts']
    if not f.get('meta'):return 'meta'
    if not snapshot['meta_verificable'] or snapshot['ambiguedad_esencial']:return 'criterio'
    for key in ['inicio','fin']:
        if key not in f:return key
        try:date.fromisoformat(f[key])
        except ValueError:return key
    if date.fromisoformat(f['fin']) < date.fromisoformat(f['inicio']):return 'fin'
    for key in ['situacion','obstaculos','principal','habilidades','apoyos','disponibilidad']:
        if key not in f:return key
    if f.get('mini_aprobadas')!='true':return 'mini'
    if f.get('tareas_aprobadas')!='true':return 'tareas'
    for key in ['papel','nota','meta_nota','papeles','pared']:
        if key not in f:return key
    return 'final'


QUESTIONS={
 'meta':'¿Cuál es tu Meta Principal?',
 'inicio':'¿En qué fecha quieres empezar, con día, mes y año?',
 'fin':'¿Cuál es tu fecha límite, con día, mes y año?',
 'situacion':'¿Cuál es tu situación actual respecto a esta meta?',
 'obstaculos':'¿Qué obstáculos podrían impedir que alcances esta meta?',
 'principal':'De esos obstáculos, ¿cuál es el principal para ti?',
 'habilidades':'¿Qué habilidad necesitas desarrollar para superar ese obstáculo?',
 'apoyos':'¿Con qué personas o recursos puedes contar para lograrlo?',
 'disponibilidad':'¿Qué tiempo tienes disponible para trabajar en esta meta?',
 'papel':'¿Qué tamaño tienen tus papelógrafos, en centímetros?',
 'nota':'¿Qué tamaño tienen tus post-it pequeños ya cortados, en centímetros?',
 'meta_nota':'¿Qué tamaño tiene el post-it grande de tu Meta Principal?',
 'papeles':'¿Cuántos papelógrafos tienes disponibles?',
 'pared':'¿Qué ancho disponible tienes para colocar los papelógrafos juntos?'
}


def cash_schedule(f):
    """Confirmed regular month-end income: reserve the next month's spending."""
    needed=['inicio','fin','saldo','ingreso','gasto','reserva','gastos_inicio_pagados','cobro_fin_mes']
    if f.get('tipo')!='ahorro' or not all(k in f for k in needed) or f['cobro_fin_mes']!='true':
        return None
    a,b=date.fromisoformat(f['inicio']),date.fromisoformat(f['fin'])
    if b.day!=calendar.monthrange(b.year,b.month)[1] or b<a:
        return None
    balance=Decimal(f['saldo']);expense=Decimal(f['gasto']);income=Decimal(f['ingreso'])
    def row(day,reserve):
        return {'fecha':day.isoformat(),'saldo':float(balance),'reserva':float(reserve),'libre':float(balance-reserve)}
    rows=[row(a,Decimal(0) if f['gastos_inicio_pagados']=='true' else expense)]
    month=a.replace(day=1);first=True
    while month<=b:
        pay=month.replace(day=calendar.monthrange(month.year,month.month)[1])
        if not first or f['gastos_inicio_pagados']!='true':
            balance-=expense
        if a<=pay<=b:
            balance+=income
            rows.append(row(pay,Decimal(f['reserva']) if pay==b else expense))
        first=False;month=(month.replace(day=28)+timedelta(days=4)).replace(day=1)
    return rows


def business_windows(f):
    needed=['fin','entrega_habiles','reposicion_habiles','entrega_lun_vie','recogida_sabados']
    if f.get('tipo')!='empresa' or not all(k in f for k in needed) or f['entrega_lun_vie']!='true':
        return None
    delivery_days=int(f['entrega_habiles']);replacement_days=int(f['reposicion_habiles'])
    if not 1<=delivery_days<=30 or not 1<=replacement_days<=30:return None
    final=date.fromisoformat(f['fin'])
    while final.weekday()>4:final-=timedelta(days=1)
    def previous_business(day,count):
        for _ in range(count):
            day-=timedelta(days=1)
            while day.weekday()>4:day-=timedelta(days=1)
        return day
    replacement_dispatch=previous_business(final,delivery_days)
    normal_delivery=previous_business(replacement_dispatch,replacement_days)
    # Pickups may happen Saturday; transit starts on the next delivery business day.
    normal_dispatch=normal_delivery
    for _ in range(50):
        normal_dispatch-=timedelta(days=1)
        if normal_dispatch.weekday()==6 or (normal_dispatch.weekday()==5 and f['recogida_sabados']!='true'):
            continue
        arrival=normal_dispatch
        for _ in range(delivery_days):
            arrival+=timedelta(days=1)
            while arrival.weekday()>4:arrival+=timedelta(days=1)
        if arrival<=normal_delivery:break
    return {'cobro_y_envio_normal_maximo':normal_dispatch.isoformat(),
            'entrega_normal_y_pedido_reposicion_maximo':normal_delivery.isoformat(),
            'recepcion_y_reenvio_reposicion_maximo':replacement_dispatch.isoformat(),
            'entrega_reposicion_maximo':final.isoformat()}


def calculations(f, include_calendar=True):
    out=[]
    if f.get('inicio') and f.get('fin'):
        a=date.fromisoformat(f['inicio']);b=date.fromisoformat(f['fin'])
        if b < a:return 'ERROR: fecha límite anterior al inicio.'
        n=(b-a).days+1
        scale='días' if n<=14 else 'semanas' if n<=65 else 'meses'
        out.append(f'CALENDARIO CALCULADO: inicio {a}, fin {b}, {n} días inclusivos; escala provisional {scale}.')
        if n<=370:
            weekdays=['lunes','martes','miércoles','jueves','viernes','sábado','domingo']
            out.append('Cantidad de días reales: '+', '.join(f'{name}: {sum((a+timedelta(days=k)).weekday()==idx for k in range(n))}' for idx,name in enumerate(weekdays)))
            if include_calendar:
                out.append('Fechas y días reales: '+', '.join(f'{a+timedelta(days=k)} {weekdays[(a+timedelta(days=k)).weekday()]}' for k in range(n)))
        needed=['saldo','ingreso','gasto','reserva','objetivo','gastos_inicio_pagados','cobro_fin_mes']
        if f.get('tipo')=='ahorro' and all(k in f for k in needed) and f['cobro_fin_mes']=='true':
            months=[];d=a.replace(day=1)
            while d<=b:
                pay=d.replace(day=calendar.monthrange(d.year,d.month)[1])
                if a<=pay<=b:months.append(pay)
                d=(d.replace(day=28)+timedelta(days=4)).replace(day=1)
            count=len(months);expenses=count-(1 if f['gastos_inicio_pagados']=='true' else 0)
            balance=Decimal(f['saldo'])+count*Decimal(f['ingreso'])-max(0,expenses)*Decimal(f['gasto'])
            free=balance-Decimal(f['reserva']);gap=max(Decimal(0),Decimal(f['objetivo'])-free)
            out.append(f'FLUJO CALCULADO: saldo inicial {f["saldo"]}; {count} cobros de {f["ingreso"]}; {max(0,expenses)} gastos mensuales PENDIENTES de {f["gasto"]}; saldo final {balance}; reserva {f["reserva"]}; libre {free}; brecha {gap}. No descontar el mes inicial pagado otra vez.')
            schedule=cash_schedule(f)
            if schedule:
                out.append('CAJA CALCULADA: '+json.dumps(schedule)+'. La reserva intermedia financia el mes siguiente; no vuelve a descontarse del saldo. Revisar cualquier libre negativo antes de proponer el plan.')
    if f.get('tipo')=='empresa' and all(k in f for k in ['unidades','precio','costo','empaque','publicidad']):
        n=Decimal(f['unidades']);net=n*(Decimal(f['precio'])-Decimal(f['costo'])-Decimal(f['empaque']))-Decimal(f['publicidad'])
        out.append(f'UTILIDAD CALCULADA sin reposición: {net}. Reserva adicional no mejora la utilidad.')
        repl=None
        if 'reposicion' in f:repl=Decimal(f['reposicion'])
        elif all(k in f for k in ['reposicion_caja','reposicion_empaque','reposicion_envio']):repl=sum(Decimal(f[k]) for k in ['reposicion_caja','reposicion_empaque','reposicion_envio'])
        if repl is not None:out.append(f'Costo total de una reposición {repl}; utilidad con UNA reposición {net-repl}.')
        windows=business_windows(f)
        if windows:
            out.append('FECHAS LÍMITE CALCULADAS con una reposición: '+json.dumps(windows)+'. Los diez cobros normales deben estar confirmados ANTES de sus envíos. No programar cierres normales después del último envío; revisiones posteriores solo verifican entregas. Fijar cantidades y minutos por fecha, incluido empaque nuevo de reposición y confirmación final; no usar ventanas sin sesiones.')
    if all(k in f for k in ['papel','meta_nota']):
        w,h=json.loads(f['papel']);mw,mh=json.loads(f['meta_nota']);zone=max(18,mw+3)
        out.append(f'GEOMETRÍA CALCULADA: ancho útil de periodos {w-6} cm en papeles previos, {w-6-zone} cm en el final; zona MP x={w-3-zone} a {w-3}. No entregar montaje antes del motor.')
    return '\n'.join(out)
