# Mario aprende: laboratorio para el aula

Compará cómo cambia una política de aprendizaje por refuerzo entre etapas guardadas. El panel reúne mediciones, errores observables y clips del mismo nivel; los resultados pueden mejorar o empeorar.

**Sesión:** `teaching_20260916` · **Estado:** preparada para entrenar · **Actualizado:** 2026-09-16 07:05 UTC.

[Guía docente: clase de 35–45 minutos](GUIA_DOCENTE.md) · [Datos y configuración de esta sesión](../../results/teaching_20260916/manifest.json) · [Proyecto y experimentos anteriores](../../README.md)

Este panel mantiene la misma ruta `docs/aula/README.md` cuando se publican nuevas sesiones. Los reportes anteriores quedan en sus carpetas de resultados. GitHub muestra la última versión subida; no transmite el entrenamiento local en vivo. El acceso depende de los permisos del repositorio.

## Para mostrar en clase

1. Mirá la primera etapa y anotá una predicción.
2. Compará la misma semilla en otra etapa: primero el comienzo, después el tramo final.
3. Contrastá la impresión visual con las cinco pruebas, la posición máxima y la bandera.
4. Describí un error observable y una hipótesis; buscá evidencia para distinguirlas.

## Qué pasó hasta ahora

Ya está evaluado el punto de partida. Hace falta otra etapa comparable para medir el cambio de esta sesión.

![Gráfico de evolución de todas las etapas comparables](../../results/teaching_20260916/progress.png)

El eje horizontal mide entrenamiento **adicional de esta sesión**. Las decisiones de la tabla son acumuladas y pueden incluir entrenamiento previo. La banda muestra el mínimo y máximo de las pruebas; no es un intervalo de confianza. La posición x es una coordenada del nivel, no un porcentaje completado.

| Etapa | Minutos adicionales | Decisiones acumuladas | Media x | Mediana x | Mín.–máx. x | Bandera |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Inicio: modelo con 102,400 decisiones previas | 0,0 | 102.400 | 649,6 | 688,0 | 300–1.127 | 0/5 |

| Etapa | Recompensa nativa media | Rachas sin progreso | Pruebas con alguna racha |
| --- | ---: | ---: | ---: |
| Inicio: modelo con 102,400 decisiones previas | 575,8 | 0 | 0/5 |

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

[Evaluación completa en JSON](../../results/teaching_20260916/stages/00_baseline/evaluation.json)

| Semilla | Máx. x | Última x | Recompensa nativa | Final del intento | Rachas | Mayor racha (decisiones) | Evidencia |
| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 101 | 300 | 300 | 236,0 | fin sin bandera; causa no identificada | 0 | 1 | [comienzo](../../results/teaching_20260916/stages/00_baseline/seed-101/beginning.gif) · [tramo final](../../results/teaching_20260916/stages/00_baseline/seed-101/ending.gif) · [traza CSV](../../results/teaching_20260916/stages/00_baseline/seed-101/trace.csv) · [último fotograma](../../results/teaching_20260916/stages/00_baseline/seed-101/last-frame.png) |
| 202 | 688 | 688 | 620,0 | fin sin bandera; causa no identificada | 0 | 10 | [comienzo](../../results/teaching_20260916/stages/00_baseline/seed-202/beginning.gif) · [tramo final](../../results/teaching_20260916/stages/00_baseline/seed-202/ending.gif) · [traza CSV](../../results/teaching_20260916/stages/00_baseline/seed-202/trace.csv) · [último fotograma](../../results/teaching_20260916/stages/00_baseline/seed-202/last-frame.png) |
| 303 | 314 | 314 | 251,0 | fin sin bandera; causa no identificada | 0 | 1 | [comienzo](../../results/teaching_20260916/stages/00_baseline/seed-303/beginning.gif) · [tramo final](../../results/teaching_20260916/stages/00_baseline/seed-303/ending.gif) · [traza CSV](../../results/teaching_20260916/stages/00_baseline/seed-303/trace.csv) · [último fotograma](../../results/teaching_20260916/stages/00_baseline/seed-303/last-frame.png) |
| 404 | 819 | 819 | 730,0 | fin sin bandera; causa no identificada | 0 | 78 | [traza CSV](../../results/teaching_20260916/stages/00_baseline/seed-404/trace.csv) |
| 505 | 1.127 | 1.127 | 1.042,0 | fin sin bandera; causa no identificada | 0 | 31 | [traza CSV](../../results/teaching_20260916/stages/00_baseline/seed-505/trace.csv) |

| Comienzo, semilla 101, decisiones 1–36 | Tramo final, semilla 101, decisiones 1–36 |
| --- | --- |
| ![Comienzo, semilla 101, decisiones 1–36](../../results/teaching_20260916/stages/00_baseline/seed-101/beginning.gif) | ![Tramo final, semilla 101, decisiones 1–36](../../results/teaching_20260916/stages/00_baseline/seed-101/ending.gif) |

**Para discutir:** ¿qué se observa al terminar este intento? ¿Qué evidencia distingue un salto tardío, una repetición de acciones o un límite de decisiones? La causa específica requiere revisar los clips; la posición por sí sola no la identifica.

## Material conservado y próximas sesiones

Los checkpoints `.zip` se guardan localmente; todavía no hay una publicación de pesos confirmada en este manifiesto. Descargar el código de GitHub no incluye esos modelos. El manifiesto registra sus rutas para quien tenga esa copia local.

El repositorio conserva los reportes, las métricas y las muestras publicadas. Los logs detallados permanecen locales.

[Informe de esta sesión](../../results/teaching_20260916/INFORME.md) · [Guía docente](GUIA_DOCENTE.md)

Sesiones conservadas:

- [teaching_20260916](../../results/teaching_20260916/INFORME.md)

Para actualizar el mismo panel después de generar nuevas evaluaciones:

```sh
.venv/bin/python lesson_report.py --manifest results/teaching_20260916/manifest.json --repo-root .
```

La actualización del panel es local hasta que se confirma y se sube a GitHub. No ejecuta aprendizaje ni modifica los pesos del modelo.
