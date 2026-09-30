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

106 tests pasaron después de cambiar la ruta activa. Incluyen pruebas heredadas de compatibilidad; ese número no representa 106 conversaciones reales. Las pruebas de la nueva ruta cubren cero tareas, tarea compartida, fechas y ciclos, cobertura de periodos de 1 a 730 días, máximo 3 columnas, MP fuera de columnas, conservación de hechos, importación/PDF y cierre sin API.

Se renderizaron y revisaron visualmente portada, papelógrafo final y leyenda del PDF. Se comprobó por extracción que los cuatro PDF mantienen todas las etiquetas, detalles y evidencias. No se midieron papelógrafos físicos: el montaje es una guía proporcional y el alumno adapta el espaciado.

## Límites de la evidencia

No se certifican 30 o 100 conversaciones completas simultáneas con esta versión. La prueba anterior de 30 primeras respuestas no equivale a eso. No se promete exactitud semántica absoluta ni latencia garantizada; las propuestas se presentan al alumno para aceptar o ajustar. El resultado se descarga y comparte manualmente, sin envío automático por correo/WhatsApp.
