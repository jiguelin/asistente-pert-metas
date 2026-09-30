# Asistente PERT Chart de Metas — app para el taller

**Estado:** los cuatro casos de prueba anteriores produjeron planes y PDF válidos, pero un caso real de salud quedó bloqueado durante más de cinco minutos al preparar tareas. La aplicación no está certificada para el evento. Las 96 pruebas locales pasan; los 30 primeros mensajes simultáneos ya probados no equivalen a 30 cierres completos.

## Corrección de latencia (septiembre de 2026)

Los pasos conversacionales usan las reglas esenciales sin adjuntar la guía de montaje completa. Si faltan los días disponibles, se pregunta ese dato antes de generar tareas. Las recurrencias se proponen compactas, sin enumerar cientos de fechas. En salud y aprendizaje, las tareas se generan como datos estructurados: Python suma sus pasos, expande las sesiones y comprueba capacidad y dependencias antes de presentarlas. Finanzas y empresa conservan su propuesta conversacional y la validación final completa. Estos borradores breves usan razonamiento bajo en el mismo modelo; la revisión semántica sigue siendo obligatoria y el cierre usa razonamiento medio. Cada turno de conversación tiene un presupuesto total de 90 segundos, como máximo tres borradores y ninguna repetición automática del SDK; al agotarlo, se cierra la lectura del flujo y se conserva el mensaje pendiente. El alumno ve la etapa actual, sin recibir borradores sin validar.

El cierre físico mantiene la guía y los controles completos. Python expande reglas recurrentes exactas y el revisor semántico recibe esas reglas junto con cantidades calculadas; el plan y PDF conservan cada sesión real. El cierre tiene un presupuesto de espera de 120 segundos y tres borradores como máximo. Si una revisión se interrumpe, el reintento reutiliza el borrador terminado en la misma sesión. Cambiar historia, modelo o hechos descarta ese borrador; cerrar la sesión también lo pierde. Estos límites acotan la espera, pero no garantizan una respuesta válida antes de ellos ni certifican 30 cierres simultáneos. Las pruebas locales verifican cancelación, conservación de contexto, preguntas faltantes y límites de intentos con respuestas simuladas. La regresión con IA real debe registrarse por separado.

## Corrección de aclaraciones (septiembre de 2026)

La meta verificada se conserva durante la conversación. Se revisa de nuevo solo ante un cambio esencial atribuido al último mensaje del alumno, no por sinónimos de ánimo ni cambios de situación actual. Energía, entusiasmo o felicidad junto a un resultado observable se mantienen como valoraciones personales sin métricas impuestas. Si una aclaración esencial no basta, el asistente propone una comprobación sencilla para aceptar, en vez de repetir definiciones abstractas. Los avances importados se reevalúan a partir de su historial completo; no se confía en un certificado de meta escrito en el archivo.

Las regresiones nuevas simulan extractores inconsistentes para comprobar el control de continuidad; por sí solas no prueban comprensión de un modelo real.

## Qué hace

- Chat con una sola pregunta por turno, basado en INSTRUCTIONS_APP.txt y la guía operativa v9, con registro de hechos acreditados y secuencia controlada.
- Entrada de texto o grabación desde el micrófono; la respuesta es escrita.
- El asistente propone mini metas y tareas. Antes del montaje final, genera un plan estructurado y ejecuta `motor_pert.verificar(plan)`; si falla, no lo declara definitivo.
- Descarga el resultado completo en PDF y el avance en JSON. Tras cerrar o recargar, el alumno puede volver a importar su JSON.
- Acceso con una contraseña común para el taller. La clave de API del organizador reside exclusivamente en los secretos de Streamlit.

## Instalar localmente

```bash
python -m pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edita secrets.toml localmente; coloca OPENAI_API_KEY y EVENT_PASSWORD.
python -m streamlit run app.py
```

**Nunca pegues la clave de API en GitHub ni en el chat de soporte.** `.streamlit/secrets.toml` está excluido mediante `.gitignore`. La suscripción de ChatGPT y la facturación de la API son independientes.

## Publicar en GitHub + Streamlit Community Cloud

1. Crea un repositorio GitHub (privado si quieres mantener el método fuera del código público) y sube esta carpeta **sin** el archivo real `secrets.toml`. Un repositorio privado puede servir una app pública, pero confirma la configuración de visibilidad en Streamlit.
2. En Streamlit Community Cloud crea una app desde el repositorio con entrada `app.py`.
3. En **Advanced settings → Secrets** copia los valores reales siguiendo `secrets.toml.example`. La contraseña `metas` es fácil de adivinar y compartir: rota la contraseña después del taller. La app verifica la contraseña vigente también para sesiones ya abiertas.
4. Consulta el consumo real en OpenAI Platform durante el piloto y el evento. No hay presupuesto máximo ni límite de turnos configurado en esta app; los US$20 mencionados eran solo una pregunta sobre costos. Si se agota el saldo de API, recarga y permite que el alumno reintente su mensaje.
5. La QA completó los cuatro casos y30 primeras respuestas simultáneas con API real. Esto no equivale a30 montajes finales simultáneos ni100 alumnos. Consulta consumo y límites de la cuenta en OpenAI Platform durante el evento.
6. Prueba en iPhone y Android la grabación, permisos, PDF, importación y envío del archivo desde las opciones de compartir del teléfono. El botón de descarga es el mecanismo garantizado por la app; compartir un PDF como archivo desde un iframe de Streamlit no está implementado ni certificado.
7. Comparte la URL y contraseña para un piloto del taller. Guarda el avance durante el trabajo; si la API falla, la aplicación permite reintentar sin perder el mensaje.

## Controles de calidad y límites conocidos

El motor comprueba días inclusivos, continuidad de periodos, sesiones, carga por día/semana, dependencias, flujo/reserva financiera y posiciones geométricas. El modelo debe revisar sentido y evidencia. Si el modelo no genera un plan que supere la validación en tres intentos o agota el tiempo de espera, la app conserva el mensaje y el punto de reparación en la sesión, y bloquea el PDF definitivo. Un segundo control interno revisa los borradores antes de mostrarlos, incluyendo criterio, calendario, tareas y coherencia semántica. Las pruebas con API real siguen siendo necesarias.

El archivo de avance debe descargarse antes de cerrar la página. No hay cuentas ni recuperación automática. La app no envía correo ni WhatsApp automáticamente: el alumno descarga el PDF y lo adjunta desde su teléfono. No hay versión BYOK en este paquete; tendría que usar otro despliegue sin la clave del organizador.

## Pruebas sin crédito de API

```bash
python -m unittest discover -s tests -v
```

`tests/test_product.py` prueba un inventario completo, el PDF, bloqueo por fechas/capacidad, y restauración con revalidación. `tests/test_streamlit.py` prueba la contraseña, su rotación y una pregunta inicial con API simulada. `tests/test_contingencies.py` valida rutas opcionales, courier y capacidad sin sumar alternativas. Estas pruebas **no** sustituyen pruebas de punta a punta con un modelo real.

## Modelo

El modelo de planificación por defecto es gpt-5.4. Se configura con PERT_MODEL; OPENAI_MODEL pertenece al prototipo anterior. No hay límite de presupuesto ni turnos.

## Archivos de referencia

`resources/SKILL.md` y `EJEMPLOS_CALIDAD_PERT.txt` conservan el paquete 0.3.6 como referencia. La app usa `INSTRUCTIONS_APP.txt` (7897 caracteres) y la guía operativa v9 adaptada a la API. El PDF `Paso_10.pdf` proviene del material del taller. `motor_pert.py` proviene de la copia local auditada del verificador v4; el ZIP de distribución 0.3.6 no lo incluía. Antes de publicar, comparar con la versión del verificador instalada en el complemento privado si puede leerse.
