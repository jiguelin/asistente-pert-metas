# Asistente PERT Chart de Metas

App del taller: convierte el cuaderno del alumno en un mapa visual de resultados y acciones significativas. No es una agenda ni un planificador de sesiones.

## Flujo activo

`app.py` usa `visual_assistant.py`, `visual_plan.py` y `visual_pdf.py`.

1. Recoge solo lo que falte: meta reconocible, inicio y fin, punto de partida, obstáculos, principal, habilidades y apoyos. Una pregunta por turno. Aprovecha información adelantada y no persigue sinónimos de energía o ánimo.
2. Propone mini metas en lenguaje de logro y tareas principales opcionales, con fechas orientativas y comprobaciones sencillas. El obstáculo principal queda destacado, con una estrategia para afrontarlo desde el inicio. Hay de cero a tres tareas por resultado; una tarea compartida se representa una sola vez.
3. El alumno acepta o ajusta la ruta. Una aceptación breve de la propuesta presente genera el montaje y PDF sin otra llamada al modelo.
4. Python distribuye periodos reales en hasta tres columnas por papelógrafo horizontal. Post-it pequeños, MP en zona final fuera de columnas, leyenda completa y revisión semanal. No se preguntan horas, medidas, papel disponible ni pared. El esquema es relativo y orientativo.

## Latencia y calidad

La extracción y la propuesta usan llamadas separadas, breves, con el modelo configurado. No hay cadena de revisores ni calendario diario. Una reparación estructural como máximo, dentro de un plazo total de 90 segundos; sin reintentos automáticos de la llamada. El mensaje pendiente se conserva si falla.

La validación comprueba fechas, cobertura temporal, IDs, notas de resultados con evidencia, número de tareas por resultado, referencias, ciclos, precedencias, densidad relativa y MP final. El modelo revisa significado y coherencia al generar; la presencia de una evidencia no garantiza por sí sola su calidad semántica. Se requieren pruebas reales de propuestas, además de tests unitarios.

Los módulos antiguos de sesiones y capacidad se conservan para compatibilidad con avances anteriores y pruebas de regresión; no gobiernan la nueva entrevista ni se usan para fabricar sesiones vacías. El transporte de API y sus límites se reutilizan desde `pert_assistant.py`. Los archivos actuales de reglas son `resources/INSTRUCTIONS_APP.txt` y `resources/GUIA_OPERATIVA_PERT_FISICO.txt`; las otras referencias históricas no se añaden al prompt activo.

## Acceso, voz y archivos

- Contraseña común mediante `EVENT_PASSWORD`. Su rotación cierra el acceso de sesiones antiguas.
- API del organizador en secretos de Streamlit (`OPENAI_API_KEY`), nunca en el repositorio.
- Texto o audio desde el micrófono, respuesta escrita.
- Descargar PDF y compartir el archivo por WhatsApp/correo desde el teléfono. La app no envía mensajes automáticamente.
- Guardar avance JSON antes de cerrar o recargar; no hay cuentas ni almacenamiento permanente de conversaciones. La importación revalida planes. Una propuesta pendiente importada se reconstruye y se presenta otra vez antes de finalizar.
- No hay límite de dólares, de turnos ni versión BYOK en este despliegue.

## Ejecutar

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Configurar `OPENAI_API_KEY` y `EVENT_PASSWORD` en los secretos de Streamlit. `PERT_MODEL` selecciona el modelo; por defecto `gpt-5.4`. La transcripción se configura con `TRANSCRIPTION_MODEL`.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

`test_visual.py` cubre la nueva ruta, cero tareas, tarea compartida, fechas/ciclos, conservación de listas, montaje sin IA después de aceptar, PDF e importación. `test_streamlit.py` verifica autenticación, rotación, reintento y conservación del historial con API simulada. Las pruebas históricas siguen verificando importaciones y módulos antiguos.

Las pruebas anteriores de 30 primeras respuestas simultáneas no certifican 30 conversaciones completas con la nueva versión. La disponibilidad del servicio, límites de API, uso simultáneo y permisos del micrófono en cada teléfono requieren validación separada; no se afirma capacidad para 100 alumnos.
