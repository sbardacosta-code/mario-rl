# Mario aprende: guía para una clase de 35 a 45 minutos

Abrir el [panel del aula](README.md). Contiene las etapas guardadas, sus métricas y muestras de juego. La clase puede darse con los resultados ya grabados: no hace falta esperar a que termine un entrenamiento en vivo.

**Objetivo:** al terminar, el grupo debe poder describir qué recibe el agente, qué puede hacer, qué señal intenta optimizar y qué evidencia permite decir que juega mejor. Una partida vistosa por sí sola no alcanza.

## Antes de la clase

1. Comprobar que la cuenta del profesor puede abrir el repositorio y los GIF. Mientras el repositorio sea privado, el enlace requiere acceso autorizado.
2. Abrir el panel, esta guía y dos etapas separadas en el tiempo. Usar la misma semilla en ambas para la primera comparación.
3. Cargar las animaciones antes de proyectar. Para trabajar sin conexión, descargar o clonar el repositorio con sus archivos y abrir los GIF con un visor local. Los enlaces relativos y las imágenes también funcionan en un visor Markdown local.
4. Revisar el estado de la sesión: un reporte que dice «en curso» contiene únicamente lo ya evaluado. Una etapa pendiente o incompleta no es un resultado cero.
5. Leer los límites del experimento: World 1-1, una semilla de entrenamiento y varias pruebas del mismo nivel. Descargar el código del repositorio no incluye los pesos `.zip`. Si el panel enlaza una versión de modelos publicada, se descargan por separado desde ese enlace; si no, permanecen locales.

## 0–5 minutos: formular una predicción

Mostrar el comienzo de la etapa inicial sin adelantar las cifras finales. Preguntar: «¿Qué esperás que mejore primero: caminar, saltar a tiempo o terminar el nivel? ¿Cómo lo medirías?» Anotar dos predicciones comprobables.

La etapa inicial de una sesión puede ser un modelo entrenado anteriormente. Consultar su etiqueta y sus decisiones acumuladas antes de llamarla «sin entrenar». El experimento histórico sí conserva la red inicial sin entrenamiento, que ya avanzaba por casualidad al muestrear acciones.

## 5–12 minutos: explicar el ciclo de aprendizaje

| Concepto | En este proyecto | Pregunta para el grupo |
| --- | --- | --- |
| Observación | Cuatro imágenes consecutivas, grises, de 84 × 84 píxeles | ¿Por qué una sola imagen puede no mostrar hacia dónde se mueve Mario? |
| Acción | Esperar, derecha, derecha + salto, derecha + correr, derecha + correr + salto | ¿Qué estrategias quedan fuera si no puede ir a la izquierda? |
| Recompensa | Señal numérica del entorno; se suma durante los fotogramas de una acción | ¿Es la misma cosa que tocar la bandera? |
| Política | Una red transforma las imágenes en probabilidades de esas acciones | ¿Puede elegir acciones distintas ante una situación parecida? |
| Episodio | Un intento hasta que termina o alcanza el límite de decisiones | ¿Un límite de tiempo equivale a morir? |
| Actualización | PPO usa experiencias recientes para ajustar los pesos | ¿Mirar una grabación modifica al modelo? |

Una decisión mantiene los botones durante hasta cuatro fotogramas del emulador. Por eso una decisión, un fotograma y una actualización de la red son unidades distintas. En este proyecto, la red recibe imágenes; las coordenadas que aparecen en los reportes se usan para medir y explicar el resultado.

El ciclo es **observar → elegir una acción → recibir una nueva observación y recompensa → reunir experiencias → ajustar los pesos → repetir**. PPO alterna interacción con el entorno y optimización usando pequeños lotes de experiencias. La política no recibe una explicación humana del error ni entiende Mario como una persona. [Artículo original de PPO](https://arxiv.org/abs/1707.06347).

## 12–22 minutos: observar las etapas y los errores

Comparar el clip inicial y el tramo final de una misma semilla en dos etapas. El tramo final muestra qué sucede cerca del cierre del intento; si el intento fue breve, ambos clips pueden solaparse. Los clips son extractos y sus rótulos identifican etapa y decisiones; el CSV conserva el recorrido medido.

Usar una ficha por observación:

| Etapa y semilla | Evidencia observable | Hipótesis | Qué habría que comprobar |
| --- | --- | --- | --- |
| Completar al mirar el clip | «Repite el salto y deja de aumentar su posición» | «Tal vez la acción se volvió demasiado repetitiva» | Frecuencia de acciones en el CSV y otras semillas |
| Completar al mirar otra etapa | «En esta prueba supera la posición donde antes terminaba» | «Podría haber mejorado el momento del salto» | Repetir con más intentos y revisar los otros clips |

Separar las frases «terminó cerca de x = …» y «murió por este enemigo». La primera puede salir de las mediciones. La segunda necesita inspeccionar el video y puede seguir siendo incierta: un número de posición no identifica una causa. «Se trancó» significa aquí una racha prolongada sin aumentar su máximo avance, según el umbral del protocolo; no significa que el sistema detecte automáticamente una pared.

Preguntar: «¿Mejoró en todas las semillas o solamente en una? ¿Qué error aparece menos? ¿Apareció otro?». Si no mejora, conservar ese resultado: es una oportunidad para explicar que entrenar ajusta parámetros, pero no garantiza aprender una conducta útil dentro del tiempo disponible.

## 22–30 minutos: leer el gráfico como un experimento

La posición máxima es la coordenada horizontal más lejana del nivel; no es un porcentaje de nivel completado ni una distancia desde cero. Usar la media junto con la mediana y el rango: un intento excepcional puede subir la media. La bandera se cuenta por separado.

Las semillas de evaluación fijan el muestreo de acciones en el mismo nivel; no generan cinco mundos nuevos. Durante estas evaluaciones, la política conserva sus pesos. En modo estocástico elige según sus probabilidades; en modo determinista elige la acción preferida. Para una comparación, mantener el mismo modo y protocolo. Evaluar periódicamente en un entorno separado y repetir los intentos ayuda a distinguir aprendizaje de variabilidad, aunque pocas pruebas siguen dando evidencia limitada. [Guía de evaluación de Stable Baselines3](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html#how-to-evaluate-an-rl-algorithm).

La curva puede subir y bajar. Mostrar todas las etapas evita contar una historia formada solamente por los mejores momentos. Si se señala una etapa para la demostración porque obtuvo el mayor avance, decir que fue seleccionada con esos resultados: no es una prueba independiente de superioridad.

Los parámetros de esta sesión son una configuración para probar, no «los mejores» de manera universal. Una tasa de aprendizaje menor reduce la magnitud de los ajustes; el umbral KL permite detener antes una actualización si la política cambia demasiado según esa medida. El coeficiente de entropía favorece conservar diversidad de acciones. Ninguno garantiza completar el nivel. Si se cambian varios a la vez, la comparación describe el conjunto y no identifica qué cambio causó el resultado.

## 30–35 minutos: el primer fracaso también enseña

Los experimentos históricos están en el [README del proyecto](../../README.md). Con tres pruebas y un presupuesto de aprendizaje equivalente, el modelo con recompensa nativa alcanzó una posición media de **296**, y el modelo con recompensa multiplicada por **0,01** llegó a **434**. La red inicial sin entrenar alcanzó aproximadamente **1.585**. Los tres obtuvieron **0 de 3 niveles completos**.

El cambio de escala mejoró ese piloto frente a la configuración original, pero siguió por debajo de la red inicial. No demostró que Mario hubiera aprendido a terminar el nivel. Los datos de esa comparación están en [ab_comparison.json](../../results/reward_scaled/ab_comparison.json).

Multiplicar la recompensa por 0,01 cambia las magnitudes usadas al aprender. Para leer los resultados, este proyecto conserva la recompensa nativa en sus evaluaciones. El escalado no añade un profesor que le indique cuándo saltar. Las recompensas de entrenamiento con distintas escalas y las pérdidas de valor resultantes no son puntuaciones de calidad directamente comparables.

## 35–45 minutos: actividad y discusión opcionales

En grupos, elegir dos etapas previamente definidas y completar una observación por semilla. Pedir una conclusión de dos frases: una sobre la evidencia y otra sobre lo que todavía no puede asegurarse.

Preguntas de cierre:

- ¿Qué justificaría decir «aprendió a pasar este obstáculo» y qué exigiríamos para decir «juega bien»?
- ¿Qué cambiarías en el próximo experimento y qué mantendrías fijo para poder interpretarlo?
- ¿Alcanzar mayor recompensa siempre significa llegar más lejos o terminar el nivel?
- ¿Qué pasaría al probar otro nivel? ¿Tenemos evidencia de que lo resolvería?
- Si una configuración cambia varios parámetros a la vez y mejora, ¿podemos saber cuál fue responsable?

Una buena respuesta cita pruebas concretas, reconoce las regresiones y evita atribuir intención, comprensión o recuerdos humanos a los pesos de la red.

## Cómo continuar sin perder la historia

Guardar una carpeta nueva por sesión y conservar sus checkpoints y evaluaciones. Actualizar el panel mediante `lesson_report.py` y subir los archivos del reporte a GitHub mantiene el mismo enlace del aula. Cada sesión conserva además su informe dentro de su carpeta de resultados, de modo que las siguientes no sobrescriben su evidencia.

El entrenamiento puede reanudarse desde un checkpoint. Eso conserva los pesos y el estado del optimizador, pero no reconstruye exactamente el estado del emulador, un lote incompleto ni toda la secuencia aleatoria anterior. Mantener el presupuesto y la configuración en el manifiesto permite explicar qué se comparó realmente.

## Referencias para preparar la explicación

- [Entorno gym-super-mario-bros](https://github.com/Kautenja/gym-super-mario-bros): juego y API utilizados.
- [Artículo de PPO](https://arxiv.org/abs/1707.06347): algoritmo de aprendizaje.
- [Consejos de Stable Baselines3](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html): evaluación y límites prácticos.
