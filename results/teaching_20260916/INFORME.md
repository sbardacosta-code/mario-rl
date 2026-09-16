# Mario aprende: laboratorio para el aula

Compará cómo cambia una política de aprendizaje por refuerzo entre etapas guardadas. El panel reúne mediciones, errores observables y clips del mismo nivel; los resultados pueden mejorar o empeorar.

**Sesión:** `teaching_20260916` · **Estado:** en curso · **Actualizado:** 2026-09-16 07:49 UTC.

[Guía docente: clase de 35–45 minutos](../../docs/aula/GUIA_DOCENTE.md) · [Datos y configuración de esta sesión](manifest.json) · [Proyecto y experimentos anteriores](../../README.md)

Este panel mantiene la misma ruta `docs/aula/README.md` cuando se publican nuevas sesiones. Los reportes anteriores quedan en sus carpetas de resultados. GitHub muestra la última versión subida; no transmite el entrenamiento local en vivo. El acceso depende de los permisos del repositorio.

## Para mostrar en clase

1. Mirá la primera etapa y anotá una predicción.
2. Compará la misma semilla en otra etapa: primero el comienzo, después el tramo final.
3. Contrastá la impresión visual con las cinco pruebas, la posición máxima y la bandera.
4. Describí un error observable y una hipótesis; buscá evidencia para distinguirlas.

## Qué pasó hasta ahora

Entre la primera y la última etapa comparable, la posición máxima media **subió: 649,6 → 1.372,2 píxeles**. La última etapa alcanzó la bandera en **0 de 5 pruebas**. Es una descripción de estas pruebas del mismo nivel; no demuestra desempeño general ni mejora estable.

![Gráfico de evolución de todas las etapas comparables](progress.png)

El eje horizontal mide entrenamiento **adicional de esta sesión**. Las decisiones de la tabla son acumuladas y pueden incluir entrenamiento previo. La banda muestra el mínimo y máximo de las pruebas; no es un intervalo de confianza. La posición x es una coordenada del nivel, no un porcentaje completado.

| Etapa | Minutos adicionales | Decisiones acumuladas | Media x | Mediana x | Mín.–máx. x | Bandera |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Inicio: modelo con 102,400 decisiones previas | 0,0 | 102.400 | 649,6 | 688,0 | 300–1.127 | 0/5 |
| Etapa 1: 15 min adicionales | 15,0 | 262.500 | 893,4 | 686,0 | 310–1.663 | 0/5 |
| Etapa 2: 30 min adicionales | 30,0 | 414.928 | 1.372,2 | 1.149,0 | 1.126–2.021 | 0/5 |

| Etapa | Recompensa nativa media | Rachas sin progreso | Pruebas con alguna racha |
| --- | ---: | ---: | ---: |
| Inicio: modelo con 102,400 decisiones previas | 575,8 | 0 | 0/5 |
| Etapa 1: 15 min adicionales | 812,0 | 0 | 0/5 |
| Etapa 2: 30 min adicionales | 1.290,4 | 0 | 0/5 |

## Cómo se midió

Semillas previstas: **101, 202, 303, 404, 505**. El muestreo se reinicia para cada prueba; las semillas cambian las acciones muestreadas en World 1-1, no el diseño del nivel. La evaluación usa pesos congelados y recompensa nativa. La configuración de aprendizaje registrada es:

| Parámetro | Valor |
| --- | --- |
| Multiplicador de recompensa al entrenar | `0.01` |
| Tasa de aprendizaje | `0.0001` |
| Umbral KL objetivo | `0.02` |
| Coeficiente de entropía | `0.01` |
| Semilla de entrenamiento | `123` |
| Segundos previstos por etapa | `900` |

Modo de evaluación: **estocástico (acciones muestreadas)**. Límite por intento: **3.000 decisiones**. Una racha se registra al pasar **120 decisiones sin aumentar el máximo x previo**, según el protocolo. Puede incluir saltos o movimiento dentro de una zona ya recorrida; no detecta automáticamente paredes ni la causa de una muerte.

Se muestran todas las etapas registradas, incluidas las regresiones. Los promedios excluyen evaluaciones incompletas o con protocolo distinto. Un intento parcial, si existe, queda documentado en su JSON. Si se eligió una etapa para demostrarla, esa selección se etiqueta y no sustituye la última etapa.

Los clips son extractos del comienzo y del final de cada prueba grabada; pueden solaparse en episodios cortos. No todas las semillas necesitan tener video: cada fila conserva su traza y las métricas. Las duraciones y los límites de captura exactos están en `evaluation.json`.

## Etapas y evidencia

### Inicio: modelo con 102,400 decisiones previas

Etapa `00_baseline` · 0,0 minutos adicionales · 102.400 decisiones acumuladas.

[Evaluación completa en JSON](stages/00_baseline/evaluation.json)

| Semilla | Máx. x | Última x | Recompensa nativa | Final del intento | Rachas | Mayor racha (decisiones) | Evidencia |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 300 | 300 | 236,0 | fin sin bandera; causa no identificada | 0 | 1 | [comienzo](stages/00_baseline/seed-101/beginning.gif) · [tramo final](stages/00_baseline/seed-101/ending.gif) · [traza CSV](stages/00_baseline/seed-101/trace.csv) · [último fotograma](stages/00_baseline/seed-101/last-frame.png) |
| 202 | 688 | 688 | 620,0 | fin sin bandera; causa no identificada | 0 | 10 | [comienzo](stages/00_baseline/seed-202/beginning.gif) · [tramo final](stages/00_baseline/seed-202/ending.gif) · [traza CSV](stages/00_baseline/seed-202/trace.csv) · [último fotograma](stages/00_baseline/seed-202/last-frame.png) |
| 303 | 314 | 314 | 251,0 | fin sin bandera; causa no identificada | 0 | 1 | [comienzo](stages/00_baseline/seed-303/beginning.gif) · [tramo final](stages/00_baseline/seed-303/ending.gif) · [traza CSV](stages/00_baseline/seed-303/trace.csv) · [último fotograma](stages/00_baseline/seed-303/last-frame.png) |
| 404 | 819 | 819 | 730,0 | fin sin bandera; causa no identificada | 0 | 78 | [traza CSV](stages/00_baseline/seed-404/trace.csv) |
| 505 | 1.127 | 1.127 | 1.042,0 | fin sin bandera; causa no identificada | 0 | 31 | [traza CSV](stages/00_baseline/seed-505/trace.csv) |

| Comienzo, semilla 101, decisiones 1–36 | Tramo final, semilla 101, decisiones 1–36 |
| --- | --- |
| ![Comienzo, semilla 101, decisiones 1–36](stages/00_baseline/seed-101/beginning.gif) | ![Tramo final, semilla 101, decisiones 1–36](stages/00_baseline/seed-101/ending.gif) |

**Para discutir:** ¿qué se observa al terminar este intento? ¿Qué evidencia distingue un salto tardío, una repetición de acciones o un límite de decisiones? La causa específica requiere revisar los clips; la posición por sí sola no la identifica.

### Etapa 1: 15 min adicionales

Etapa `01_stage` · 15,0 minutos adicionales · 262.500 decisiones acumuladas.

[Evaluación completa en JSON](stages/01_stage/evaluation.json) · [Resumen del entrenamiento](training/01_stage/training_summary.json)

| Semilla | Máx. x | Última x | Recompensa nativa | Final del intento | Rachas | Mayor racha (decisiones) | Evidencia |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 682 | 682 | 606,0 | fin sin bandera; causa no identificada | 0 | 22 | [comienzo](stages/01_stage/seed-101/beginning.gif) · [tramo final](stages/01_stage/seed-101/ending.gif) · [traza CSV](stages/01_stage/seed-101/trace.csv) · [último fotograma](stages/01_stage/seed-101/last-frame.png) |
| 202 | 310 | 310 | 254,0 | fin sin bandera; causa no identificada | 0 | 1 | [comienzo](stages/01_stage/seed-202/beginning.gif) · [tramo final](stages/01_stage/seed-202/ending.gif) · [traza CSV](stages/01_stage/seed-202/trace.csv) · [último fotograma](stages/01_stage/seed-202/last-frame.png) |
| 303 | 1.663 | 1.663 | 1.556,0 | fin sin bandera; causa no identificada | 0 | 49 | [comienzo](stages/01_stage/seed-303/beginning.gif) · [tramo final](stages/01_stage/seed-303/ending.gif) · [traza CSV](stages/01_stage/seed-303/trace.csv) · [último fotograma](stages/01_stage/seed-303/last-frame.png) |
| 404 | 686 | 686 | 613,0 | fin sin bandera; causa no identificada | 0 | 16 | [traza CSV](stages/01_stage/seed-404/trace.csv) |
| 505 | 1.126 | 1.126 | 1.031,0 | fin sin bandera; causa no identificada | 0 | 40 | [traza CSV](stages/01_stage/seed-505/trace.csv) |

| Comienzo, semilla 101, decisiones 1–93 | Tramo final, semilla 101, decisiones 19–93 |
| --- | --- |
| ![Comienzo, semilla 101, decisiones 1–93](stages/01_stage/seed-101/beginning.gif) | ![Tramo final, semilla 101, decisiones 19–93](stages/01_stage/seed-101/ending.gif) |

**Para discutir:** ¿qué se observa al terminar este intento? ¿Qué evidencia distingue un salto tardío, una repetición de acciones o un límite de decisiones? La causa específica requiere revisar los clips; la posición por sí sola no la identifica.

### Etapa 2: 30 min adicionales

Etapa `02_stage` · 30,0 minutos adicionales · 414.928 decisiones acumuladas.

[Evaluación completa en JSON](stages/02_stage/evaluation.json) · [Resumen del entrenamiento](training/02_stage/training_summary.json)

| Semilla | Máx. x | Última x | Recompensa nativa | Final del intento | Rachas | Mayor racha (decisiones) | Evidencia |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 1.126 | 1.126 | 1.051,0 | fin sin bandera; causa no identificada | 0 | 5 | [comienzo](stages/02_stage/seed-101/beginning.gif) · [tramo final](stages/02_stage/seed-101/ending.gif) · [traza CSV](stages/02_stage/seed-101/trace.csv) · [último fotograma](stages/02_stage/seed-101/last-frame.png) |
| 202 | 1.149 | 1.149 | 1.065,0 | fin sin bandera; causa no identificada | 0 | 13 | [comienzo](stages/02_stage/seed-202/beginning.gif) · [tramo final](stages/02_stage/seed-202/ending.gif) · [traza CSV](stages/02_stage/seed-202/trace.csv) · [último fotograma](stages/02_stage/seed-202/last-frame.png) |
| 303 | 1.129 | 1.129 | 1.051,0 | fin sin bandera; causa no identificada | 0 | 16 | [comienzo](stages/02_stage/seed-303/beginning.gif) · [tramo final](stages/02_stage/seed-303/ending.gif) · [traza CSV](stages/02_stage/seed-303/trace.csv) · [último fotograma](stages/02_stage/seed-303/last-frame.png) |
| 404 | 2.021 | 2.021 | 1.943,0 | fin sin bandera; causa no identificada | 0 | 5 | [traza CSV](stages/02_stage/seed-404/trace.csv) |
| 505 | 1.436 | 1.436 | 1.342,0 | fin sin bandera; causa no identificada | 0 | 20 | [traza CSV](stages/02_stage/seed-505/trace.csv) |

| Comienzo, semilla 101, decisiones 1–148 | Tramo final, semilla 101, decisiones 74–148 |
| --- | --- |
| ![Comienzo, semilla 101, decisiones 1–148](stages/02_stage/seed-101/beginning.gif) | ![Tramo final, semilla 101, decisiones 74–148](stages/02_stage/seed-101/ending.gif) |

**Para discutir:** ¿qué se observa al terminar este intento? ¿Qué evidencia distingue un salto tardío, una repetición de acciones o un límite de decisiones? La causa específica requiere revisar los clips; la posición por sí sola no la identifica.

## Material conservado y próximas sesiones

Los checkpoints `.zip` se guardan localmente; todavía no hay una publicación de pesos confirmada en este manifiesto. Descargar el código de GitHub no incluye esos modelos. El manifiesto registra sus rutas para quien tenga esa copia local.

El repositorio conserva los reportes, las métricas y las muestras publicadas. Los logs detallados permanecen locales.

Último checkpoint local registrado: `results/teaching_20260916/training/02_stage/checkpoints/final.zip`.

[Informe de esta sesión](INFORME.md) · [Guía docente](../../docs/aula/GUIA_DOCENTE.md)

Sesiones conservadas:

- [teaching_20260916](INFORME.md)

Para actualizar el mismo panel después de generar nuevas evaluaciones:

```sh
.venv/bin/python lesson_report.py --manifest results/teaching_20260916/manifest.json --repo-root .
```

La actualización del panel es local hasta que se confirma y se sube a GitHub. No ejecuta aprendizaje ni modifica los pesos del modelo.
