# Mario aprende: plan del proyecto docente

Objetivo: que el alumnado pueda observar y medir cómo cambia una política que aprende a jugar World 1-1. No se presupone que terminará el nivel ni que cada etapa mejorará.

## Sesión de hasta tres horas

- Punto de partida: el modelo del ensayo con recompensa ×0,01, con 102.400 decisiones previas. La etapa inicial se evalúa antes de entrenar más.
- Continuación en bloques de unos 15minutos, conservando un checkpoint por bloque y el registro de todas las etapas.
- Cinco ensayos fijos por etapa: 101,202,303,404,505. Para 101,202,303 se guardan clips de las primeras 150 y últimas 75 decisiones, último fotograma y traza completa. Los clips pueden coincidir en episodios cortos.
- Auditoría final separada: 10semillas nuevas 1001–1010, aplicadas al modelo final elegido por presupuesto. No se selecciona retrospectivamente el mejor resultado para presentarlo como el final.
- El proceso reserva tiempo para las evaluaciones y el cierre; no dedica las tres horas enteras al entrenamiento. El límite absoluto queda en el manifiesto. Si una subida queda pendiente, se completa después sin entrenar más.

## Configuración candidata

| Parámetro | Valor | Motivo |
| --- | ---: | --- |
| Algoritmo | PPO con CNN | Mantener el método y las observaciones ya probadas |
| Recompensa para aprender | Nativa ×0,01 | El ensayo anterior mostró más estabilidad inicial |
| Tasa de aprendizaje |0,0001| Probar ajustes menores que 0,00025 |
| Límite KL |0,02| Detener una actualización si cambia excesivamente la política |
| Coeficiente de entropía |0,01| Mantener el incentivo de exploración |
| Entornos / CPU threads |4 /1| Configuración medida en esta Mac |
| Pasos por entorno / batch / epochs |256 /256 /4| Mantener el resto de PPO |
| Observación / repetición de acción |4 imágenes84×84 /4 frames| Conservar la representación existente |

Son parámetros candidatos, no un óptimo demostrado. Se cambian tasa de aprendizaje y límite KL juntos y se continúa un checkpoint previo: esta sesión no permite aislar el efecto de cada cambio. Un experimento causal posterior deberá variar un parámetro por vez y repetir semillas de entrenamiento.

## Qué se muestra en clase

La [galería](README.md) presenta la media, mediana, rango de distancia y niveles completos por etapa. También muestra dónde terminó cada intento y períodos de 120decisiones sin superar el máximo previo. Eso mide falta de progreso: no demuestra que Mario esté inmóvil ni identifica por sí mismo un enemigo o un pozo.

La [guía docente](GUIA_DOCENTE.md) propone una clase de 35–45minutos: predecir acciones, comparar clips, distinguir recompensa y éxito, formular hipótesis y comprobarlas. Se conservan los retrocesos y las fallas como parte del material.

## Persistencia y continuación

El enlace del repositorio y el de docs/aula permanecen estables. Cada sesión tiene una carpeta propia, con manifiesto, parámetros, métricas, clips y trazas. Las etapas anteriores no se sobrescriben. El panel principal apunta a la sesión más reciente y los informes por sesión permanecen archivados.

Los checkpoints se guardan localmente y, al completar una sesión publicada, se respaldan como archivos de una GitHub Release. Su enlace aparece en la galería solo cuando termina la subida. Se conserva el acceso configurado en el repositorio; un repositorio privado requiere colaboradores autorizados.

Al continuar desde un checkpoint se recuperan pesos y optimizador. Cada bloque reinicia el emulador y su semilla; no reproduce exactamente el estado anterior del simulador ni su generador aleatorio. La escala de recompensas debe mantenerse explícitamente en 0,01.

El programa genera resultados sin depender de una ventana del juego. La galería se actualiza al cerrar cada etapa, no frame a frame. Para interrumpir con guardado, crear un archivo `STOP` en la carpeta de la sesión. Mantener la Mac encendida y la app abierta permite que el entrenamiento local y su seguimiento continúen.

## Referencias

- [PPO y significado de sus parámetros](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html)
- [Evaluación, variabilidad y buenas prácticas de RL](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html)
- [Entorno Super Mario Bros.](https://github.com/Kautenja/gym-super-mario-bros)
