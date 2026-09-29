# Asistente PERT Chart de Metas — app para el taller

**Estado:** validación funcional aprobada en los cuatro casos (salud, finanzas, empresa y aprendizaje), con PDF completo y revisado. Las 37 pruebas locales pasan, también desde una copia independiente; 30 primeras solicitudes simultáneas a IA real respondieron correctamente. Disponible para uso individual y piloto del taller. No se han probado micrófonos/permisos en teléfonos reales ni30 cierres complejos simultáneos.

Las cuatro entrevistas iniciales fueron nuevas; las regresiones finales reutilizaron sus avances aprobados. El cierre empresarial necesitó tres borradores internos y unos10 minutos. El alumno ve únicamente el resultado que pasa los controles; el indicador muestra tiempo de espera.

## Qué hace

- Chat con una sola pregunta por turno, basado en INSTRUCTIONS_APP.txt y la guía operativa v8, con registro de hechos acreditados y secuencia controlada.
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

El motor comprueba días inclusivos, continuidad de periodos, sesiones, carga por día/semana, dependencias, flujo/reserva financiera y posiciones geométricas. El modelo debe revisar sentido y evidencia. Si el modelo no genera un plan que supere la validación en cinco intentos, la app conserva el borrador y bloquea el PDF definitivo. Un segundo control interno revisa los borradores antes de mostrarlos, incluyendo criterio, calendario, tareas y coherencia semántica. Las pruebas con API real siguen siendo necesarias.

El archivo de avance debe descargarse antes de cerrar la página. No hay cuentas ni recuperación automática. La app no envía correo ni WhatsApp automáticamente: el alumno descarga el PDF y lo adjunta desde su teléfono. No hay versión BYOK en este paquete; tendría que usar otro despliegue sin la clave del organizador.

## Pruebas sin crédito de API

```bash
python -m unittest discover -s tests -v
```

`tests/test_product.py` prueba un inventario completo, el PDF, bloqueo por fechas/capacidad, y restauración con revalidación. `tests/test_streamlit.py` prueba la contraseña, su rotación y una pregunta inicial con API simulada. `tests/test_contingencies.py` valida rutas opcionales, courier y capacidad sin sumar alternativas. Estas pruebas **no** sustituyen pruebas de punta a punta con un modelo real.

## Modelo

El modelo de planificación por defecto es gpt-5.4. Se configura con PERT_MODEL; OPENAI_MODEL pertenece al prototipo anterior. No hay límite de presupuesto ni turnos.

## Archivos de referencia

`resources/SKILL.md` y `EJEMPLOS_CALIDAD_PERT.txt` conservan el paquete 0.3.6 como referencia. La app usa `INSTRUCTIONS_APP.txt` (7558 caracteres) y la guía operativa v8 adaptada a la API. El PDF `Paso_10.pdf` proviene del material del taller. `motor_pert.py` proviene de la copia local auditada del verificador v4; el ZIP de distribución 0.3.6 no lo incluía. Antes de publicar, comparar con la versión del verificador instalada en el complemento privado si puede leerse.
