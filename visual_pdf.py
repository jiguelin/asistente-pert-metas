"""Self-contained visual roadmap export; layout is relative, not centimetric."""
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, KeepTogether
from pdf_export import _font, _p
from visual_plan import LANES

COLORS={'M':'#fff0aa','T':'#ffe0bb','H':'#d9ecfa','O':'#f8d9df','A':'#dcefd7'}

def export_visual_pdf(audit):
    p=audit['plan'];buf=BytesIO();font=_font()
    body=ParagraphStyle('visual',fontName=font,fontSize=10,leading=14,spaceAfter=6)
    small=ParagraphStyle('small',parent=body,fontSize=8,leading=11,spaceAfter=2)
    title=ParagraphStyle('title',parent=body,fontSize=22,leading=27,spaceAfter=14,textColor=colors.HexColor('#194e69'))
    heading=ParagraphStyle('heading',parent=body,fontSize=13,leading=18,spaceBefore=10,spaceAfter=8)
    doc=SimpleDocTemplate(buf,pagesize=landscape(A4),leftMargin=34,rightMargin=34,topMargin=32,bottomMargin=32,title='Mi mapa visual de metas')
    out=[]
    def add(text,style=body):out.append(_p(text,style))
    add('Mi mapa visual de metas',title);add('META PRINCIPAL',heading);add(p['meta'])
    if p.get('criterio') and p['criterio'].casefold() not in p['meta'].casefold():add(p['criterio'])
    add(f"Inicio: {p['inicio']} · Fecha límite: {p['fin']} · {audit['dias_inclusivos']} días inclusivos")
    add('Punto de partida',heading);add(p['situacion'])
    add('La piedra principal en el camino',heading);add(p['principal']);add(p['estrategia'])
    add('La ruta y sus líneas paralelas',heading);add(p['secuencia'])
    add('Cómo preparar tus papelógrafos',heading)
    add(f"Usa {len(audit['hojas'])} papelógrafo(s) horizontales. Copia las divisiones de las siguientes páginas: máximo tres columnas temporales por hoja. La última puede tener menos. No hace falta cortar las hojas.")
    add('Usa post-it pequeños (un cuarto del tamaño habitual), con ID y etiqueta corta. El texto completo queda en la leyenda. Para la Meta Principal usa un post-it normal o una tarjeta si necesitas más espacio. Reserva su zona final a la derecha, fuera de las columnas temporales.')
    add('Anota el punto de partida junto al inicio, sin crear otra columna temporal. Marca con una estrella la nota del obstáculo principal y ten presente la primera acción para afrontarlo.')
    add('La distribución es orientativa: deja separación para flechas y para mover las notas. Antes de pegarlas definitivamente, distribúyelas sin fijar y comprueba que puedes leerlas y moverlas. Adapta el espaciado al papel que tengas.')
    for s,group in enumerate(audit['hojas'],1):
        out.append(PageBreak());add(f'Papelógrafo {s} · horizontal',title)
        add('Obstáculo principal que debes vigilar: '+p['principal'],small)
        last=s==len(audit['hojas']);header=['Banda']+[p['periodos'][j]['label']+'\n'+p['periodos'][j]['inicio']+' al '+p['periodos'][j]['fin'] for j in group]+(['Zona final\nFuera de columnas'] if last else [])
        rows=[[_p(x,small) for x in header]]
        for t,name in LANES.items():
            row=[_p(name,small)]
            for j in group:
                ns=[n for n in p['notas'] if n['tipo']==t and n.get('periodo')==j]
                row.append(_p('\n\n'.join(n['id']+' · '+n['texto'] for n in ns) or 'Espacio libre',small))
            if last:row.append(_p('MP\n'+p['meta']+('\n'+p.get('criterio','') if p.get('criterio','').casefold() not in p['meta'].casefold() else '') if t=='M' else '',small))
            rows.append(row)
        zone=145 if last else 0; width=(doc.width-90-zone)/len(group)
        table=Table(rows,colWidths=[90]+[width]*len(group)+([zone] if last else []),repeatRows=1)
        styles=[('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#b9c7cc')),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8eff3')),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]
        for r,t in enumerate(LANES,1):styles.append(('BACKGROUND',(1,r),(len(group),r),colors.HexColor(COLORS[t])))
        table.setStyle(TableStyle(styles));out.append(table)
        add('Los colores son opcionales. Las etiquetas en las casillas representan post-it separados. Conserva aire entre ellos.',small)
    out.append(PageBreak());add('Leyenda de tus notas',title)
    add('Copia solo el ID y la etiqueta corta al post-it; usa esta leyenda para recordar el significado. Las fechas intermedias son orientativas. En tareas indican dónde empezar a trabajar en esa acción principal, no horas ni duración.')
    cards=[]
    note_style=ParagraphStyle('note',parent=body,fontSize=9,leading=12)
    for n in p['notas']:
        location=f"Hoja {n['hoja']} · "+(f"columna {n['columna']}" if n['tipo']!='MP' else 'zona final')
        text=f"{n['id']} · {n['texto']}\n{location} · {n['fecha']}\n{n['detalle']}"
        if n['evidencia']:text+='\nComprobación: '+n['evidencia']
        if n['para']:text+='\nContribuye a: '+', '.join(n['para'])
        cards.append(_p(text,note_style))
    if len(cards)%2:cards.append('')
    grid=Table([cards[i:i+2] for i in range(0,len(cards),2)],colWidths=[doc.width/2]*2)
    grid.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),14),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),10),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#dce3e8'))]))
    out.append(grid)
    add('Conexiones importantes',heading)
    add('Usa flechas para el orden propuesto, sin encadenar las ramas paralelas. Las contribuciones, apoyos y riesgos pueden quedarse en esta leyenda; dibuja una línea punteada solo cuando ayude a entender el mapa. No necesitas unir todas las notas.')
    labels={'antes':'va antes de (orden propuesto)'}
    labels.update({'contribuye':'contribuye a','apoyo':'apoya a','riesgo':'puede dificultar'})
    grouped={}
    byid={n['id']:n for n in p['notas']}
    for e in p['conexiones']:
        if e['tipo']=='contribuye' and e['a'] in byid[e['de']]['para']:continue
        grouped.setdefault((e['de'],e['tipo']),[]).append(e['a'])
    for (source,kind),targets in grouped.items():add(source+' '+labels[kind]+' '+', '.join(targets))
    add('Las contribuciones de cada tarea a sus resultados figuran en su ficha de la leyenda.',small)
    if not p['conexiones']:add('No necesitas flechas de dependencia para esta ruta; las fechas y la explicación indican el avance.')
    add('Cada semana: revisar, mover y avanzar',heading)
    add('Comprueba qué resultados lograste y márcalos. Mueve las notas o ajusta fechas si cambió la realidad. Revisa primero el obstáculo principal y la acción que te ayuda a afrontarlo. Añade obstáculos o apoyos relevantes cuando aparezcan. Elige el próximo paso importante y desglósalo en tu agenda o lista diaria, sin llenar el mapa de microtareas.')
    def footer(c,d):
        c.setFont(font,8);c.setFillColor(colors.HexColor('#627781'));c.drawString(34,17,'Asistente PERT Chart de Metas · mapa visual');c.drawRightString(landscape(A4)[0]-34,17,str(d.page))
    doc.build(out,onFirstPage=footer,onLaterPages=footer)
    return buf.getvalue()
