# Verificación de la ruta visual — 30 de septiembre de 2026

## Cambio de producto autorizado

Mapa de lo significativo, basado en el cuaderno del taller. No agenda ni sesiones/minutos. Obstáculo principal visible y primera acción para afrontarlo desde el inicio. Mini metas en lenguaje de logro; 0–3 tareas por resultado cuando aportan. Materiales recomendados, sin preguntar medidas ni pared. Revisión semanal dinámica.

## Conversaciones reales en la app publicada

Sesiones nuevas e independientes, con clave del taller y API del organizador. Casos ficticios. Se dieron datos de alumno y se aceptó la propuesta; no se corrigió al asistente dentro de las conversaciones. Las correcciones de software se hicieron entre sesiones.

| Caso | Propuesta | Aceptación y cierre | Resultado observado |
|---|---:|---:|---|
| Salud, 66.5 a 70 kg | 37.51 s | 0.40 s | Ruta, obstáculo principal, estrategia inicial, 4 mini metas y 3 tareas; PDF descargado |
| Financiera, S/4000 libres y reserva enero | 24.52 s | 0.44 s | Punto de partida conservado; mini metas, tareas y PDF |
| Empresarial, 10 cajas vendidas/cobradas/entregadas | 30.08 s | 0.42 s | Miedo a ofrecer tratado desde el inicio; hermana y courier conservados; PDF |
| Aprendizaje, tabla dinámica autónoma | 32.93 s | 0.41 s | Reutiliza habilidad ya aportada; no inventa obstáculo; PDF |
| Entrevista completa, caminar 5 km | 22.28 s en propuesta | 0.40 s | Una pregunta por turno; inicio → situación → obstáculos → principal → habilidad → apoyo; ninguna pregunta de horas o materiales |

Preguntas sencillas de la entrevista: 4.86–8.38 segundos. Los cierres se calculan desde la propuesta aceptada sin nuevas llamadas al modelo. Son observaciones, no garantía de latencia futura. Finanzas, empresa y entrevista se ejecutaron en 802d833; salud/aprendizaje finales en 51a3414. Los últimos cambios de exportación se comprobaron localmente con los cuatro planes reales.

## Errores detectados y corregidos

- Importante: varios hechos con el mismo campo se sobrescribían y perdían peso inicial o apoyos. Se conservan todos los elementos acreditados y se solicita consolidación.
- Importante: una cita no consecutiva podía dejar sin registrar una habilidad expresamente aportada. Citas cortas consecutivas y recuperación de etiquetas explícitas del cuaderno.
- Importante: condiciones de logro separadas de la meta podían desaparecer del encabezado del montaje. Se muestran también como condición del logro y en zona MP.
- Importante: mini metas vagas o con duración implícita incoherente. Se reforzó resultado reconocible y coherencia entre nombre y fecha; el nuevo caso de salud da un mes desde 10 de octubre hasta 10 de noviembre.
- Importante: el flujo anterior obligaba a horas, materiales, muchas revisiones y sesiones. Fue sustituido por propuesta breve y montaje determinista.
- Menor: demasiadas relaciones repetidas en el PDF. Se agrupan y las contribuciones de tareas se mantienen en sus fichas; apoyos/riesgos pueden quedarse en la leyenda sin llenar el papel de flechas.

## Verificación local

109 tests pasaron después de cambiar la ruta activa. Incluyen pruebas heredadas de compatibilidad; ese número no representa 106 conversaciones reales. Las pruebas de la nueva ruta cubren cero tareas, tarea compartida, fechas y ciclos, cobertura de periodos de 1 a 730 días, máximo 3 columnas, MP fuera de columnas, conservación de hechos, importación/PDF y cierre sin API.

Se renderizaron y revisaron visualmente portada, papelógrafo final y leyenda del PDF. Se comprobó por extracción que los cuatro PDF mantienen todas las etiquetas, detalles y evidencias. No se midieron papelógrafos físicos: el montaje es una guía proporcional y el alumno adapta el espaciado.

## Límites de la evidencia

La prueba final que se detalla abajo cubre 30 sesiones que aportan todo el cuaderno, reciben la propuesta y aceptan el cierre. No prueba 100 alumnos ni garantiza la latencia futura o todos los diálogos posibles. No se promete exactitud semántica absoluta ni latencia garantizada; las propuestas se presentan al alumno para aceptar o ajustar. El resultado se descarga y comparte manualmente, sin envío automático por correo/WhatsApp.

## Prueba final de carga — versión 7ae5515

Se abrieron 30 sesiones independientes, se esperó a tenerlas listas y se enviaron las solicitudes al mismo tiempo. Ocho casos físicos, ocho financieros, siete empresariales y siete de aprendizaje. Cada sesión aportó los datos del cuaderno y aceptó la propuesta; se descargó su avance, diagnóstico y PDF.

**Resultado: 30/30 rutas y PDF entregados, sin reintento manual del alumno.** Propuestas: 23.41–68.79 segundos. Cierre tras aceptar: 0.38–9.85 segundos. No se cambiaron plataforma, modelo ni plan de hosting para esta prueba. No son garantías de rendimiento futuro.

Las dos rondas previas terminaron 28/30 cada una y permitieron corregir: coincidencias de evidencia sensibles a mayúsculas/puntuación; diagnóstico de precedencia sin IDs/fechas concretos; punto final pegado a fecha ISO; «Ninguno.» que no activaba ausencia de obstáculo principal. Se añadieron regresiones. Las 58 extracciones guardadas de esas dos rondas avanzan ahora a propuesta al reproducirlas con el normalizador corregido. Los dos tipos de caso afectados también se repitieron en vivo con éxito antes de la carga final.

Se revalidaron los 30 planes finales y se comprobó que todos los PDF contienen las etiquetas de todas sus notas. Esto verifica integridad estructural, exportación y comportamiento bajo esa carga; no equivale a una revisión humana exhaustiva de cada afirmación generada en las 30 propuestas.
