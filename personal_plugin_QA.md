# Checkpoint posterior a intake y guía v9

Fecha: 2026-09-30. QA local, sin API/red y sin cambios en la app. Skill PDF leída y aplicada para render e inspección visual. Se leyeron CLI, intake actualizado, SKILL, guía v9 y protocolo local actualizado.

## Validación funcional

- 4 `validar` y 4 `exportar`: ok:true / rc=0.
- 30 negativos originales: bloqueados con JSON / rc=2.
- 3 controles positivos: pasan (capacidad exacta por fecha confirmada, capital inicial cero financiado con caja sin déficit, ahorro irregular confirmado).
- Todos los IDs y posiciones conservados respecto de los planes reales aprobados.
- Los cinco módulos importados coinciden byte a byte con la app actual.

| Caso | Minutos base | Reserva condicional | Papeles | Notas | Páginas PDF |
|---|---:|---:|---:|---:|---:|
| Salud v10 | 1485 | 0 | 2 | 17 | 6 |
| Finanzas v11 | 355 | 0 | 2 | 15 | 7 |
| Empresa v12 | 765 | 40 | 3 | 24 | 10 |
| Aprendizaje v8 | 1350 | 0 | 2 | 18 | 7 |

## Lectura de continuidad y contrato

Intake conserva meta/criterio aceptados y solo reabre ante un cambio esencial atribuible al último usuario. Los traces anteriores sin los nuevos campos siguen funcionando. SKILL, guía v9 y protocolo coinciden en no perseguir energía/pilas/entusiasmo/felicidad cuando hay un resultado observable; conservan preferencias sin imponer métricas. Un reporte aún vago requiere propuesta concreta y aceptación. La revisión semántica sigue siendo del agente.

El protocolo ya documenta `estado.capacidad_confirmada` y `estado.caja_confirmada`. Ambos controles positivos pasan; no hace falta inventar un patrón semanal ni exigir que todo el capital esté disponible al inicio si hay financiación fechada.

## Defecto adicional del adaptador: corregido

Reproducción: una contingencia de empresa declarada con `max_activaciones:2` se recompilaba como 1 y devolvía ok:true. Se avisó al agente raíz ANTES de editar. La guarda nueva en CLI bloquea la reducción silenciosa y explica que la reposición automática solo cubre una incidencia. No se modificaron módulos copiados.

Regresión adicional comprobada en `contingency_count_regression.json`; suite completa repetida después del ajuste. El caso de una incidencia conserva 765+40 min y las cuatro rutas alternativas.

## Revisión visual final

Se renderizaron e inspeccionaron las 30 páginas (contactos y páginas individuales para los puntos densos). La revisión de empresa contó con lectura independiente de sus 10 páginas. No se observaron pérdidas, texto recortado, superposiciones, glifos dañados ni conflictos con márgenes/footer. La renderización final posterior al último cambio del CLI coincide por píxeles con la inspeccionada.

Mejoras menores de paginación heredadas del exportador compartido, sin afectar integridad o lectura:

- Finanzas, página 2: última fila de caja sola con cabecera repetida; el salto previo al inventario deja mucho espacio vacío.
- Empresa, página 2: esfuerzo/proyección empresarial en una página muy poco ocupada.
- Empresa, páginas 8-9: descripción de la ruta detectada el 2026-11-05 y sus minutos quedan en páginas distintas.

No se alteró el exportador para conservar su identidad con la app. No son errores nuevos de cálculo o del adaptador. Los PDFs son QA intermedio, no entrega final.

## Evidencia

- `post_copy_results.json`, `post_copy_extra_results.json`: suite completa posterior a copia/guarda.
- `checkpoint_post_copy.json`: conteos, hashes e identidad visual final.
- `contingency_count_regression.json`: bloqueo de reducción 2→1; reproducible con `python test_cli_contingency_count.py` después de la suite principal.
- `empresa_visual_pre_copy.md`: inspección independiente de empresa.
- `test_cli_review.py`, `test_cli_extra.py`: reproducir en ese orden, escriben QA en `/tmp/pert_cli_qa_review`.
- Render final íntegro: `/tmp/pert_cli_visual_final_after_guard` (30 PNG y 7 contactos).

No hay nuevo bloqueo funcional del CLI en los cuatro casos. El alcance de reposición automática sigue siendo una incidencia/40 minutos/semana laboral sin festivos; otros alcances requieren diseño y revisión específicos, sin rebajarlos en secreto.
