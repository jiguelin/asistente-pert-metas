"""Active workshop flow: collect notebook facts, propose a roadmap, lay it out."""
import json
import re
import time
from copy import deepcopy
from datetime import date
from pathlib import Path
import pert_assistant as transport
from intake import context, normalize, QUESTIONS
from visual_plan import audit_visual, proposal_text, final_text

AssistantError=transport.AssistantError
TRACE=transport.TRACE
PROGRESS=transport.PROGRESS
FINAL_WORK=transport.FINAL_WORK
KEYS=['meta','criterio','inicio','fin','situacion','obstaculos','principal','habilidades','apoyos']
INTAKE=deepcopy(transport.INTAKE_SCHEMA)
INTAKE['properties']['hechos']['items']['properties']['campo']['enum']=KEYS
PROMPT='''Extrae exclusivamente los hechos del alumno para un mapa visual, sin hacer un plan.
Usa hechos que dijo o propuestas que aceptó; no inventes. Cada hecho lleva cita literal corta de un mensaje de usuario e índice de ese mensaje (desde 0). Fechas ISO completas.
Campos: meta, criterio, inicio, fin, situacion, obstaculos, principal, habilidades, apoyos. Devuelve UN hecho por campo, consolidando todos sus datos vigentes en el valor: situación incluye todas las medidas iniciales y recursos; apoyos incluye todas las personas y recursos. Nunca devuelvas solo el último elemento de una lista. No recojas horas ni materiales. Reutiliza datos de todo el historial; un dato nuevo sustituye al anterior si el usuario lo corrige. Si hay saldo inicial o inventario ya hay situación actual.
Meta verificable: resultado reconocible o cantidad suficiente. Caminar 5 km con buena energía y pesar 70 kg con abdomen marcado permiten avanzar. No persigas sinónimos de energía, ánimo o felicidad ni impongas condiciones clínicas. Una meta exclusivamente vaga sí necesita aclaración. ambiguedad_esencial solo si falta el logro central, usando un término literal del alumno; en otro caso null.
meta_cambiada y cambio_meta_cita solo si el último mensaje cambia el logro central. Meta admitida no se reabre por preferencias personales.
Si ya señaló el principal, extráelo. Con un solo obstáculo inequívoco puede ser el principal; no lo elijas de una lista. «Ninguno» es válido. «No sé» no acredita habilidad ni apoyo: omite el campo, salvo si ya existía un dato confirmado. No omitas habilidades o apoyos aceptados. No conviertas el silencio en aceptación.
Devuelve solo JSON. U0,U1 son alumnos; A es asistente.'''

def obj(props):return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
S={'type':'string'}
NOTE=obj({'id':S,'tipo':{'type':'string','enum':['M','T','H','O','A','MP']},'texto':S,'detalle':S,'fecha':S,'evidencia':S,'para':{'type':'array','items':S}})
EDGE=obj({'de':S,'a':S,'tipo':{'type':'string','enum':['antes','contribuye','apoyo','riesgo']}})
PLAN=obj({**{k:S for k in ['meta','inicio','fin','situacion','principal','estrategia','secuencia']},'notas':{'type':'array','items':NOTE},'conexiones':{'type':'array','items':EDGE}})
TURN=obj({'reply':S})
ROOT=Path(__file__).parent

def instructions():return (ROOT/'resources/INSTRUCTIONS_APP.txt').read_text()

def call(client,model,messages,prompt,schema,name,usage,tokens=4200):
    r=transport._create(client,_stream_retry=False,model=model,instructions=prompt,input=messages,
        text={'format':{'type':'json_schema','name':name,'strict':True,'schema':schema}},
        reasoning={'effort':'low'},max_output_tokens=tokens,store=False)
    transport.add_usage(usage,r)
    return json.loads(r.output_text)

def accepted(text):
    return bool(re.fullmatch(r'(?:s[ií](?:[, ]+(?:acepto|apruebo|me sirve|est[aá] bien))?|acepto|apruebo|de acuerdo|me sirve|ok|perfecto)[.! ]*',text.strip(),re.I))

def normalize_visual(payload,users,known=None,accepted_goal=None):
    # The extractor may emit one item per list member. Validate each quote
    # before merging, rather than letting the last one erase the earlier facts.
    grouped={}
    for h in payload['hechos']:
        one={**payload,'hechos':[h]}
        valid=normalize(one,users)['facts']
        k=h['campo']
        if k in valid:
            if k in ['situacion','obstaculos','habilidades','apoyos']:
                grouped.setdefault(k,[])
                if h['valor'] not in grouped[k]:grouped[k].append(h['valor'])
    snap=normalize(payload,users,known,accepted_goal)
    for k,values in grouped.items():snap['facts'][k]='; '.join(values)
    return snap


def next_stage(s):
    f=s['facts']
    if not f.get('meta'):return 'meta'
    if not s['meta_verificable'] or s.get('ambiguedad_esencial'):return 'criterio'
    for k in ['inicio','fin']:
        try:date.fromisoformat(f[k])
        except (KeyError,ValueError,TypeError):return k
    if f['fin']<f['inicio']:return 'fin'
    for k in ['situacion','obstaculos','principal','habilidades','apoyos']:
        if not f.get(k):return k
    return 'propuesta'

def respond(client,model,messages,today_lima,known_facts=None,accepted_goal=None):
    token=transport.TURN_DEADLINE.set(time.monotonic()+90)
    usage={'input_tokens':0,'output_tokens':0}
    try:
        if not messages:return QUESTIONS['meta'],False,usage
        known=dict(known_facts or {})
        cached=known.pop('_visual_proposal',None)
        if cached and accepted(messages[-1]['content']) and len(messages)>1 and messages[-2]['content'].endswith('¿Te sirve esta ruta o quieres ajustar algo?'):
            audit_visual(cached)
            usage['snapshot']={'facts':{**known,'_visual_proposal':cached},'goal_validation':accepted_goal}
            return 'Preparando el montaje de tu mapa…',True,usage
        transport._progress('Ordenando lo que compartiste de tu cuaderno…')
        users,transcript=context(messages)
        payload=call(client,model,transcript,PROMPT+f'\nHoy: {today_lima}.',INTAKE,'visual_intake',usage,2200)
        snap=normalize_visual(payload,users,known,accepted_goal);f=snap['facts']
        for prev,cur in zip(messages,messages[1:]):
            if prev['role']!='assistant' or cur['role']!='user':continue
            answer=cur['content'].strip()
            if re.search(r'no s[eé]|no entiendo|ay[uú]dame',answer,re.I):continue
            for k in ['situacion','obstaculos','principal','habilidades','apoyos']:
                if prev['content'].endswith(QUESTIONS[k]):f.setdefault(k,answer)
        if str(f.get('obstaculos','')).lower().strip() in ['ninguno','ningún obstáculo','no tengo obstáculos']:f.setdefault('principal','Ninguno identificado')
        usage['snapshot']=snap
        stage=next_stage(snap)
        last=messages[-1]['content']
        if stage in QUESTIONS and not (stage in ['habilidades','apoyos','principal'] and re.search(r'no s[eé]|ay[uú]dame|prop[oó]n',last,re.I)):
            return QUESTIONS[stage],False,usage
        if stage!='propuesta':
            goal={'criterio':'Aclara el logro central con una sola pregunta. Si ya hubo una aclaración, propone una formulación reconocible a aceptar sin perseguir sinónimos.',
                  'principal':'Propón cuál de los obstáculos declarados es el principal y cómo afecta la meta; pregunta solo si lo reconoce como principal.',
                  'habilidades':'Propón una habilidad sencilla que permita afrontar el obstáculo principal y pregunta solo si le sirve.',
                  'apoyos':'Propón un recurso accesible sin inventar personas disponibles y pregunta solo si podría usarlo.'}[stage]
            data=call(client,model,messages,instructions()+'\n'+goal,TURN,'visual_question',usage,700)
            reply=data['reply']
            if max(reply.count('?'),reply.count('¿'))>1:raise AssistantError('No pude completar la pregunta. Tu avance se conserva.')
            return reply,False,usage
        transport._progress('Proponiendo mini metas y acciones importantes…')
        prompt=instructions()+'''\nGenera una propuesta estructurada de mapa visual, no texto conversacional.
Mantén exactamente meta, inicio y fin de los hechos. No inventes cifras como hechos ni garantías de viabilidad. Puedes proponer cantidades intermedias razonables, claramente propuestas, sin imponer progresiones lineales. Mantén las restricciones aportadas. Si hay una contradicción, explica la limitación en estrategia sin simular que se resolvió.
Estrategia: una explicación concreta y breve de cómo empezar a afrontar el obstáculo principal usando habilidades/apoyos/tareas. Si no hay obstáculo no lo inventes. Identifica una primera acción concreta para afrontarlo desde el inicio; no basta decir «mantener constancia» o «usar apoyos». No tienes que bloquear todas las líneas hasta resolverlo.
Notas: IDs M1..., T1..., H1..., O1..., A1... y MP. Cada etiqueta tiene 2–5 palabras (máximo 7); detalle conserva lo necesario. M y MP expresan resultado logrado y evidencia sencilla. No impongas mini metas por mes ni repitas el logro final. Cada mini meta debe permitir responder sí/no con una comprobación sencilla. Evita «base estable», «avance consolidado», «cerca del objetivo», «en marcha» o «la mayoría» sin definir el resultado. Puedes proponer «Primer mes de práctica completado» con evidencia de la pauta acordada seguida, o «Primeras 3 ventas cobradas», sin detallar sesiones. Un resultado preparatorio debe preceder a sus consecuencias, por ejemplo acordar la pauta antes de completar un mes siguiéndola. Propón normalmente 2–5 mini metas significativas, sin cuota obligatoria. Una a tres tareas por resultado como máximo, y cero cuando no hacen falta; normalmente bastan 2–5 tareas en todo el mapa. No tareas por hábito diario ni sesiones. No propongas «armar el PERT», «ordenar el cuaderno» ni «hacer un plan» como sustituto del trabajo necesario para lograr la meta. Sí cabe acordar una pauta específica con un apoyo cuando eso habilite acciones reales. Una tarea compartida aparece una sola vez, para=[IDs de resultados]. Para otras notas para=[].
Fecha en notas: M/MP fecha de logro; T ubicación orientativa para empezar la acción principal; H/O/A inicio salvo razón aportada. MP fecha final. Todas dentro del plazo. No es una hora ni duración. Evidencia puede estar vacía solo para T/H/O/A.
Incluye obstáculos, habilidades y apoyos relevantes declarados. Puedes agrupar equivalentes con detalle completo, sin más de 6 notas de un tipo en el mismo periodo. Identifica el principal en la nota de obstáculo. No inventes apoyos o habilidades ya adquiridas.
Conexiones: pocas y relevantes. «antes» solo de un resultado M a otro resultado o tarea que realmente depende de haberlo logrado; fecha previa <= siguiente. Para T hacia resultados usa «contribuye»: su fecha representa el inicio, no la terminación. H/O/A usan contribuye/riesgo/apoyo. No encadenes tareas independientes. Explica el orden y las líneas paralelas en secuencia, máximo 80 palabras. No describas papelógrafos, columnas, materiales ni montaje en secuencia: la aplicación los calcula después. Incluye solo relaciones relevantes y no conectes indiscriminadamente todas las notas a MP.
Antes de responder revisa significado de resultados, fidelidad a la meta, estrategia del principal, fechas y simplicidad. No añadas minutos, presupuesto horario ni medidas.\nHECHOS: '''+json.dumps(f,ensure_ascii=False)
        plan=call(client,model,messages,prompt,PLAN,'visual_proposal',usage,5200)
        for k in ['meta','inicio','fin','situacion','principal']:plan[k]=f[k]
        try:audit_visual(plan)
        except ValueError as exc:
            # One bounded structural repair only, not a chain of semantic reviews.
            plan=call(client,model,[{'role':'user','content':json.dumps(plan,ensure_ascii=False)}],prompt+'\nCorrige este error estructural: '+str(exc),PLAN,'visual_repair',usage,5200)
            for k in ['meta','inicio','fin','situacion','principal']:plan[k]=f[k]
            audit_visual(plan)
        f['_visual_proposal']=plan
        return proposal_text(plan)+'\n\n¿Te sirve esta ruta o quieres ajustar algo?',False,usage
    finally:transport.TURN_DEADLINE.reset(token)

def build_final(client,model,messages,today_lima,ready_snapshot=None):
    plan=(ready_snapshot or {}).get('facts',{}).get('_visual_proposal')
    if not plan:raise AssistantError('Falta la propuesta de ruta. Pídeme que la prepare para revisarla contigo.')
    return audit_visual(plan),[],{'input_tokens':0,'output_tokens':0}

final_message=final_text
