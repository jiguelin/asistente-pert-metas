# Asistente PERT Chart de Metas — app para el taller

**Estado:** revisión de calidad en curso. Las cuatro conversaciones de la primera versión detectaron errores de calendario, flujo financiero y finalización. Esta revisión corrige el flujo y tiene 17 pruebas locales aprobadas; la revisión financiera ya completó el PDF con API real; falta aprobar las cuatro conversaciones completas con la revisión final y comprobar audio en teléfonos. No compartir con alumnos todavía.

## Qué hace

- Chat con una sola pregunta por turno, basado en INSTRUCTIONS_APP.txt y la guía operativa v7, con registro de hechos acreditados y secuencia controlada.
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
5. Prueba una conversación completa con API real; comprueba el consumo de tokens y audio en Usage; luego haz cuatro casos completos y una prueba simultánea de 30 navegadores.
6. Prueba en iPhone y Android la grabación, permisos, PDF, importación y envío del archivo desde las opciones de compartir del teléfono. El botón de descarga es el mecanismo garantizado por la app; compartir un PDF como archivo desde un iframe de Streamlit no está implementado ni certificado.
7. Solo entonces comparte la URL y contraseña a los alumnos.

## Controles de calidad y límites conocidos

El motor comprueba días inclusivos, continuidad de periodos, sesiones, carga por día/semana, dependencias, flujo/reserva financiera y posiciones geométricas. El modelo debe revisar sentido y evidencia. Si el modelo no genera un plan que supere la validación en tres intentos, la app conserva el borrador y bloquea el PDF definitivo. Un segundo control interno revisa los borradores antes de mostrarlos, incluyendo criterio, calendario, tareas y coherencia semántica. Las pruebas con API real siguen siendo necesarias.

El archivo de avance debe descargarse antes de cerrar la página. No hay cuentas ni recuperación automática. La app no envía correo ni WhatsApp automáticamente: el alumno descarga el PDF y lo adjunta desde su teléfono. No hay versión BYOK en este paquete; tendría que usar otro despliegue sin la clave del organizador.

## Pruebas sin crédito de API

```bash
python -m unittest discover -s tests -v
```

`tests/test_product.py` prueba un inventario completo, el PDF, bloqueo por fechas/capacidad, y restauración con revalidación. `tests/test_streamlit.py` prueba la contraseña, su rotación y una pregunta inicial con API simulada. Estas pruebas **no** sustituyen pruebas de punta a punta con un modelo real.

## Modelo

El modelo de planificación por defecto es gpt-5.4. Se configura con PERT_MODEL; OPENAI_MODEL pertenece al prototipo anterior. No hay límite de presupuesto ni turnos.

## Archivos de referencia

`resources/SKILL.md` y `EJEMPLOS_CALIDAD_PERT.txt` conservan el paquete 0.3.6 como referencia. La app usa `INSTRUCTIONS_APP.txt` (6872 caracteres) y la guía operativa v7 adaptada a la API. El PDF `Paso_10.pdf` proviene del material del taller. `motor_pert.py` proviene de la copia local auditada del verificador v4; el ZIP de distribución 0.3.6 no lo incluía. Antes de publicar, comparar con la versión del verificador instalada en el complemento privado si puede leerse.
