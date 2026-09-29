"""Readable, complete multi-page PDF from one audited inventory."""
from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path
import reportlab

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def _font() -> str:
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path(reportlab.__file__).resolve().parent / "fonts/Vera.ttf",
    ]
    for candidate in candidates:
        if candidate.exists():
            if "PertSans" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("PertSans", str(candidate)))
            return "PertSans"
    return "Helvetica"


def _p(value: object, style: ParagraphStyle) -> Paragraph:
    text=str(value or "—").replace("→", "->").replace("✓", "un visto").replace("⭐", "*")
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def export_pdf(audit: dict) -> bytes:
    plan, motor = audit["plan"], audit["motor"]
    font = _font()
    base = getSampleStyleSheet()
    title = ParagraphStyle("PertTitle", parent=base["Title"], fontName=font,
                           fontSize=18, leading=24, textColor=colors.HexColor("#263543"))
    heading = ParagraphStyle("PertHeading", parent=base["Heading2"], fontName=font,
                             fontSize=12, leading=16, spaceBefore=13, spaceAfter=5,
                             textColor=colors.HexColor("#194E69"))
    body = ParagraphStyle("PertBody", parent=base["BodyText"], fontName=font,
                          fontSize=9.2, leading=13, spaceAfter=4)
    small = ParagraphStyle("PertSmall", parent=body, fontSize=8.1, leading=11,
                           spaceAfter=2)
    cell = ParagraphStyle("PertCell", parent=small, fontSize=7.8, leading=10)
    top = ParagraphStyle("PertTop", parent=title, alignment=TA_CENTER)
    stream = BytesIO()

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont(font, 8)
        canvas.setFillColor(colors.HexColor("#697682"))
        canvas.drawString(1.65 * cm, 1.1 * cm, "Asistente PERT Chart de Metas")
        canvas.drawRightString(A4[0] - 1.65 * cm, 1.1 * cm, f"Página {doc.page}")
        canvas.restoreState()

    doc = BaseDocTemplate(stream, pagesize=A4, title="Mi PERT Chart de Metas",
                          leftMargin=1.65 * cm, rightMargin=1.65 * cm,
                          topMargin=1.6 * cm, bottomMargin=1.75 * cm)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=decorate))
    out = [_p("MI PERT CHART DE METAS", top), Spacer(1, .3 * cm)]
    mp = next(n for n in audit["notas"] if n["tipo"] == "MP")
    out.extend([_p("Meta Principal", heading),
                _p(mp.get("criterio") or mp.get("detalle") or mp["texto"], body),
                _p(f"Inicio: {plan['inicio']}  |  Límite: {plan['fin']}  |  "
                   f"Duración inclusiva: {motor['dias_inclusivos']} días", body),
                _p(f"{audit['notas_pequenas']} notas pequeñas y una Meta Principal grande; "
                   f"{motor['papelografos']} papelógrafos; "
                   f"{motor['minutos_totales']} minutos de trabajo programado.", body)])
    context=plan.get('contexto',{})
    if context.get('situacion_actual'):
        out.extend([_p('Situación actual',heading),_p(context['situacion_actual'],body)])
    if plan.get('consolidaciones'):
        out.append(_p('Se agruparon tareas con el mismo procedimiento; se conservan todas sus sesiones y minutos.',body))

    out.append(_p("Montaje en tres pasos", heading))
    for step in ("1. Prepara los papelógrafos horizontales, únelos de izquierda a derecha y dibuja las filas.",
                 "2. Marca las columnas temporales con los límites de abajo y pega cada nota en su papel, fila y coordenada.",
                 "3. Pega la Meta Principal grande en la zona final y dibuja las flechas según la lista de conexiones."):
        out.append(_p(step, body))
    out.append(_p("Para cada tarea recurrente, dibuja una línea discontinua desde su nota hasta su fecha final, sin agregar post-it. Las flechas por evento se conectan a la fecha indicada en esa línea. Traza las flechas por los espacios libres, sin cruzar notas.",body))
    m = plan["materiales"]
    out.append(_p(f"Medidas en cm: papel {m['papel'][0]} × {m['papel'][1]}, "
                  f"nota pequeña {m['nota'][0]} × {m['nota'][1]} (un cuarto de post-it), "
                  f"Meta Principal {m['meta'][0]} × {m['meta'][1]}. "
                  "Las coordenadas son desde la esquina superior izquierda del papel.", body))
    out.append(_p("Columnas y zona final", heading))
    for c in audit["columnas"]:
        out.append(_p(f"Papel {c['papel']}, columna {c['columna']}: "
                      f"{c['inicio']} a {c['fin']}; x = {c['x_inicial']}–{c['x_final']} cm.", body))
    z = audit["zona_mp"]
    out.append(_p(f"Papel {z['papel']}: zona de la Meta Principal "
                  f"x = {z['x_inicial']}–{z['x_final']} cm, fuera de todas las columnas.", body))
    out.append(_p("Densidad comprobada", heading))
    for d in motor["densidad"]:
        out.append(_p(f"Papel {d['papel']}, columna {d['columna']}: "
                      f"{sum(d['conteo'].values())} notas; "
                      f"{d['capacidad_fila']-d['maximo_usado']} plazas libres "
                      "en la fila más ocupada.", body))
    if motor.get('minutos_condicionales_maximos'):
        out.append(_p(f"Trabajo base: {motor['minutos_base']:g} min. Reserva adicional: hasta {motor['minutos_condicionales_maximos']:g} min solo si se activa una contingencia. Las rutas alternativas no se suman ni se repiten.",body))
    if plan.get('economia'):
        e=plan['economia']
        out.append(_p('Proyección empresarial',heading))
        out.append(_p(f"Si se logran las ventas previstas: ingreso {e['ingreso_previsto']:.2f}; costo del inventario {e['costo_inventario']:.2f}; empaques normales {e['empaques_normales']:.2f}; publicidad {e['publicidad']:.2f}. Ganancia sin reposición: {e['utilidad_sin_reposicion']:.2f}; con una reposición de {e['costo_una_reposicion']:.2f}: {e['utilidad_con_una_reposicion']:.2f}.",body))
        out.append(_p(f"Capital disponible {e['capital_disponible']:.2f}; hasta {e['costos_pendientes_maximos']:.2f} para los costos posteriores al inventario ya disponible, incluida una reposición. Importes en la moneda de tu meta.",body))

    if plan.get('finanzas') and plan.get('caja'):
        out.append(_p('Dinero reservado y libre', heading))
        out.append(_p('El saldo incluye el dinero reservado. Solo la columna libre queda disponible después de separar las obligaciones previstas.', body))
        rows=[['Fecha','Saldo','Reservado','Libre']]+[[r['fecha'],f"{r['saldo']:.2f}",f"{r['reserva']:.2f}",f"{r['libre']:.2f}"] for r in plan['caja']]
        table=Table(rows,colWidths=[5*cm,4*cm,4*cm,4*cm],repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),font),('FONTSIZE',(0,0),(-1,-1),9),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EDF3F6')),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#CAD5DC')),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
        out.append(table)
    out.append(PageBreak())
    out.append(_p("Inventario y leyenda completa", title))
    out.append(_p("Fila 1: resultados. Fila 2: tareas. Fila 3: habilidades. "
                  "Fila 4: obstáculos. Fila 5: apoyos. Colores: amarillo para "
                  "resultados y MP, naranja para tareas, azul para habilidades, "
                  "rosa para obstáculos y verde para apoyos. "
                  "En cada post-it pequeño escribe solo su ID y texto breve; "
                  "consulta esta leyenda para fechas y detalles.", body))
    colors_by_type = {"M": "amarillo", "MP": "amarillo grande", "T": "naranja",
                      "H": "azul", "O": "rosa", "A": "verde"}
    for note in audit["notas"]:
        pos = note["posicion"]
        loc = (f"Papel {pos['papel']}; zona final; x={pos['x']}, y={pos['y']} cm"
               if note["tipo"] == "MP" else
               f"Papel {pos['papel']}, columna {pos['columna']}, fila {pos['fila']}; "
               f"x={pos['x']}, y={pos['y']} cm")
        description = (f"{note['id']} · {colors_by_type[note['tipo']]} · {note['texto']}")
        if note.get('principal'):
            description += ' · OBSTÁCULO PRINCIPAL'
        info = [description, loc, f"Fechas: {note['inicio']} a {note['fin']}"]
        if note.get('principal'):
            info.append('Marca una estrella en esta nota rosa.')
        if note.get('condicional'):
            info.append('SOLO SI OCURRE: no es trabajo obligatorio; usa una sola ruta de contingencia.')
        for key, label in (("detalle", "Detalle"), ("criterio", "Criterio"),
                           ("evidencia", "Evidencia"), ("frecuencia", "Frecuencia")):
            if note.get(key):
                info.append(f"{label}: {note[key]}")
        if note.get("minutos_totales"):
            info.append(f"Esfuerzo programado: {note['minutos_totales']} min en total")
        info.append("Predecesores/conexiones entrantes: " +
                    (", ".join(note["predecesores"]) or "ninguno"))
        info.append("Sucesores/conexiones salientes: " +
                    (", ".join(note["sucesores"]) or "ninguno"))
        out.append(KeepTogether([_p(description, heading)] + [_p(x, small) for x in info[1:]]))

    for group in plan.get('contingencias',[]):
        out.append(_p(group['id']+' · rutas de contingencia',heading))
        out.append(_p('Conserva una sola nota. Si aparece un daño, usa únicamente la ruta de su fecha de comprobación; si no hay daño, no ejecutes esta tarea. La fecha de llegada del proveedor y el día en que revisas/reenvías el paquete pueden ser distintos.',body))
        for route in group['rutas']:
            out.append(_p(f"Si se detecta en {route['activacion']['fecha']}: pedido {route['pedido']}; llegada del proveedor {route['llegada_reemplazo']}; revisión {route['revision_reemplazo']}; reenvío {route['reenvio']}; entrega prevista {route['entrega_reemplazo']}; comprobación {route['confirmacion']}.",body))
            out.append(_p('Tiempo: '+', '.join(f"{s['fecha']}: {s['minutos']:g} min" for s in route['sesiones'])+'.',small))
    out.append(_p("Flechas que debes trazar", heading))
    out.append(_p("Línea continua: requisito real. Línea discontinua: "
                  "continuidad, contribución, apoyo o riesgo. Las flechas por sesión/evento "
                  "llevan la anotación indicada.", body))
    grouped={}
    for edge in audit["flechas"]:
        grouped.setdefault((edge['desde'],edge['hacia']),[])
        if edge['tipo'] not in grouped[(edge['desde'],edge['hacia'])]:
            grouped[(edge['desde'],edge['hacia'])].append(edge['tipo'])
    out.append(_p('Dibuja una sola flecha por pareja de IDs; conserva en ella todas las anotaciones indicadas.',body))
    for (source,target),labels in grouped.items():
        out.append(_p(f"{source} → {target} · {'; '.join(labels)}", small))
    out.append(_p("Seguimiento", heading))
    out.append(_p("Marca ✓ cuando completes una nota. Si hay retraso, marca X, "
                  "escribe la nueva fecha y revisa las notas que dependen de ella.", body))
    doc.build(out)
    return stream.getvalue()
