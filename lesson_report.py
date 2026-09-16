#!/usr/bin/env python3
"""Build the Spanish classroom index and an archived report from a session manifest.

Paths in the manifest are relative to the repository. Media and trace paths in
evaluation.json are relative to that evaluation file. No training is performed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import statistics
from urllib.parse import quote


COMPARISON_KEYS = (
    "environment", "seeds", "max_decisions", "deterministic", "seed_method",
    "action_space", "action_repeat", "observation_shape", "reward",
    "stall_threshold_decisions", "stall_definition",
)
STATUS = {"preparing": "preparando evaluación inicial", "prepared": "preparada para entrenar", "running": "en curso", "completed": "finalizada", "interrupted": "interrumpida", "failed": "interrumpida por error"}
END_REASONS = {
    "level_completed": "bandera alcanzada",
    "episode_ended_without_flag": "fin sin bandera; causa no identificada",
    "decision_limit": "límite de decisiones",
}


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def within(root: Path, relative: str | Path) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes repository: {relative}")
    return path


def number(value: object, digits: int = 0) -> str:
    if value is None:
        return "—"
    result = f"{float(value):,.{digits}f}"
    return result.replace(",", "_").replace(".", ",").replace("_", ".")


def cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def link(label: str, target: Path, document: Path, image: bool = False) -> str:
    relative = quote(os.path.relpath(target, document.parent), safe="/._-")
    return f"{'!' if image else ''}[{cell(label)}]({relative})"


def existing_link(label: str, target: Path, document: Path) -> str:
    return link(label, target, document) if target.is_file() else "—"


def finite(value: object, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite {label}: {value}")
    return result


def load_stages(repo: Path, manifest: dict) -> list[dict]:
    stages = []
    expected_seeds = manifest.get("configuration", {}).get("eval_seeds")
    reference_protocol = None
    seen_ids = set()
    last_seconds = -1.0
    for source in manifest.get("stages", []):
        stage = dict(source)
        if not stage.get("id") or stage["id"] in seen_ids:
            raise ValueError("Stage IDs must be present and unique")
        seen_ids.add(stage["id"])
        stage["seconds"] = finite(stage.get("elapsed_training_seconds", 0), "stage elapsed seconds")
        if stage["seconds"] < last_seconds or stage["seconds"] < 0:
            raise ValueError("Stages must be ordered by nonnegative elapsed training time")
        last_seconds = stage["seconds"]
        stage["minutes"] = stage["seconds"] / 60
        stage["evaluation_file"] = within(repo, stage["evaluation_path"])
        stage["evaluation"] = None
        stage["episodes"] = []
        stage["comparable"] = False
        stage["warning"] = "Evaluación pendiente; no se interpreta como resultado cero."
        if stage["evaluation_file"].is_file():
            evaluation = read_json(stage["evaluation_file"])
            stage["evaluation"] = evaluation
            episodes = evaluation.get("episodes", [])
            protocol = evaluation.get("protocol", {})
            stage["episodes"] = episodes
            seeds = [episode["seed"] for episode in episodes]
            planned = protocol.get("seeds", [])
            for episode in episodes:
                finite(episode["max_x"], "max_x")
                finite(episode["native_reward"], "native_reward")
            signature = {key: protocol.get(key) for key in COMPARISON_KEYS}
            issues = []
            if evaluation.get("status") != "complete":
                issues.append("evaluación incompleta")
            if not planned or seeds != planned or len(set(seeds)) != len(seeds):
                issues.append("faltan pruebas planificadas o hay semillas repetidas")
            if expected_seeds is not None and planned != expected_seeds:
                issues.append("semillas distintas del manifiesto")
            if reference_protocol is None and not issues:
                reference_protocol = signature
            elif reference_protocol is not None and signature != reference_protocol:
                issues.append("protocolo distinto del de la primera evaluación completa")
            if issues:
                stage["warning"] = "; ".join(issues) + ". Excluida de las comparaciones agregadas."
            else:
                stage["comparable"] = True
                stage["warning"] = None
                distances = [float(episode["max_x"]) for episode in episodes]
                stalls = [len(episode.get("stall_events", [])) for episode in episodes]
                stage.update({
                    "mean": statistics.mean(distances),
                    "median": statistics.median(distances),
                    "minimum": min(distances),
                    "maximum": max(distances),
                    "clears": sum(bool(episode["completed"]) for episode in episodes),
                    "count": len(episodes),
                    "mean_reward": statistics.mean(float(episode["native_reward"]) for episode in episodes),
                    "stalls": sum(stalls),
                    "stall_trials": sum(count > 0 for count in stalls),
                    "mean_stalls": statistics.mean(stalls),
                })
        stages.append(stage)
    return stages


def draw_chart(stages: list[dict], output: Path, session_id: str) -> None:
    os.environ.setdefault("MPLCONFIGDIR", str(output.parent / ".matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    plt.rcParams.update({"font.size": 10, "axes.titlesize": 12, "axes.labelsize": 10})
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.2), layout="constrained")
    fig.suptitle("Mario RL · evolución de la sesión\n" + session_id, fontsize=15)
    complete = [stage for stage in stages if stage["comparable"]]
    for axis in axes.flat:
        axis.grid(axis="y", alpha=0.22)
        axis.spines[["top", "right"]].set_visible(False)
        axis.set_xlabel("Minutos de entrenamiento adicional")
    axes[0, 0].set_title("Avance: media, mediana y rango observado")
    axes[0, 0].set_ylabel("Posición máxima x (píxeles del nivel)")
    axes[0, 1].set_title("Cada semilla, sin ocultar regresiones")
    axes[0, 1].set_ylabel("Posición máxima x (píxeles del nivel)")
    axes[1, 0].set_title("Niveles completados")
    axes[1, 0].set_ylabel("Pruebas que alcanzan la bandera")
    axes[1, 1].set_title("Rachas prolongadas sin nuevo máximo x")
    axes[1, 1].set_ylabel("Rachas por prueba, media")
    if complete:
        times = [stage["minutes"] for stage in complete]
        axes[0, 0].fill_between(times, [s["minimum"] for s in complete], [s["maximum"] for s in complete], color="#cce5ef", alpha=.65, label="mínimo–máximo (no es IC)")
        axes[0, 0].plot(times, [s["mean"] for s in complete], "o-", color="#137b8c", label="media")
        axes[0, 0].plot(times, [s["median"] for s in complete], "s--", color="#ef8b2c", label="mediana")
        axes[0, 0].legend(fontsize=8, loc="best")
        seeds = [episode["seed"] for episode in complete[0]["episodes"]]
        for seed in seeds:
            values = [next(episode["max_x"] for episode in stage["episodes"] if episode["seed"] == seed) for stage in complete]
            axes[0, 1].plot(times, values, "o-", linewidth=1.2, markersize=3, label=str(seed))
        axes[0, 1].legend(title="Semilla", fontsize=8, ncol=3)
        axes[1, 0].plot(times, [s["clears"] for s in complete], "o-", color="#326f48")
        count = complete[0]["count"]
        axes[1, 0].set_ylim(-.2, count + .3)
        axes[1, 0].set_yticks(range(count + 1))
        axes[1, 0].set_ylabel(f"Pruebas con bandera (de {count})")
        axes[1, 1].plot(times, [s["mean_stalls"] for s in complete], "o-", color="#9b4560")
        axes[1, 1].set_ylim(bottom=0)
        for axis in axes.flat:
            axis.set_xlim(left=-.5, right=max(times[-1] + 1, 1))
    else:
        for axis in axes.flat:
            axis.text(.5, .5, "Todavía no hay evaluaciones\ncompletas y comparables", ha="center", va="center", transform=axis.transAxes)
    fig.savefig(output, dpi=150, facecolor="white")
    plt.close(fig)


def evaluation_asset(repo: Path, stage: dict, relative: str | None) -> Path | None:
    if not relative:
        return None
    path = (stage["evaluation_file"].parent / relative).resolve()
    if not path.is_relative_to(repo):
        raise ValueError(f"Evaluation asset escapes repository: {relative}")
    return path if path.is_file() else None


def make_report(repo: Path, manifest_path: Path, manifest: dict, stages: list[dict], document: Path, chart: Path, generated_at: str) -> str:
    guide = repo / "docs" / "aula" / "GUIA_DOCENTE.md"
    session = within(repo, manifest["session_dir"])
    config = manifest.get("configuration", {})
    complete = [stage for stage in stages if stage["comparable"]]
    content = [
        "# Mario aprende: laboratorio para el aula", "",
        "Compará cómo cambia una política de aprendizaje por refuerzo entre etapas guardadas. El panel reúne mediciones, errores observables y clips del mismo nivel; los resultados pueden mejorar o empeorar.", "",
        f"**Sesión:** `{cell(manifest['session_id'])}` · **Estado:** {STATUS.get(manifest.get('status'), cell(manifest.get('status', 'sin indicar')))} · **Actualizado:** {generated_at}.", "",
        f"{existing_link('Guía docente: clase de 35–45 minutos', guide, document)} · {link('Datos y configuración de esta sesión', manifest_path, document)} · {existing_link('Proyecto y experimentos anteriores', repo / 'README.md', document)}", "",
        "Este panel mantiene la misma ruta `docs/aula/README.md` cuando se publican nuevas sesiones. Los reportes anteriores quedan en sus carpetas de resultados. GitHub muestra la última versión subida; no transmite el entrenamiento local en vivo. El acceso depende de los permisos del repositorio.", "",
        "## Para mostrar en clase", "",
        "1. Mirá la primera etapa y anotá una predicción.",
        "2. Compará la misma semilla en otra etapa: primero el comienzo, después el tramo final.",
        "3. Contrastá la impresión visual con las cinco pruebas, la posición máxima y la bandera.",
        "4. Describí un error observable y una hipótesis; buscá evidencia para distinguirlas.", "",
        "## Qué pasó hasta ahora", "",
    ]
    if len(complete) >= 2:
        first, last = complete[0], complete[-1]
        delta = last["mean"] - first["mean"]
        direction = "subió" if delta > 0 else "bajó" if delta < 0 else "no cambió"
        content.append(f"Entre la primera y la última etapa comparable, la posición máxima media **{direction}: {number(first['mean'], 1)} → {number(last['mean'], 1)} píxeles**. La última etapa alcanzó la bandera en **{last['clears']} de {last['count']} pruebas**. Es una descripción de estas pruebas del mismo nivel; no demuestra desempeño general ni mejora estable.")
    elif complete:
        content.append("Ya está evaluado el punto de partida. Hace falta otra etapa comparable para medir el cambio de esta sesión.")
    else:
        content.append("Todavía no hay evaluaciones completas comparables. Las etapas pendientes no se cuentan como fallos ni como valores cero.")
    content += ["", link("Gráfico de evolución de todas las etapas comparables", chart, document, image=True), "",
        "El eje horizontal mide entrenamiento **adicional de esta sesión**. Las decisiones de la tabla son acumuladas y pueden incluir entrenamiento previo. La banda muestra el mínimo y máximo de las pruebas; no es un intervalo de confianza. La posición x es una coordenada del nivel, no un porcentaje completado.", "",
        "| Etapa | Minutos adicionales | Decisiones acumuladas | Media x | Mediana x | Mín.–máx. x | Bandera |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for stage in stages:
        lead = f"| {cell(stage.get('label', stage['id']))} | {number(stage['minutes'], 1)} | {number(stage.get('training_timesteps'))}"
        if stage["comparable"]:
            content.append(lead + f" | {number(stage['mean'], 1)} | {number(stage['median'], 1)} | {number(stage['minimum'])}–{number(stage['maximum'])} | {stage['clears']}/{stage['count']} |")
        else:
            content.append(lead + " | pendiente/no comparable | — | — | — |")
    content += ["", "| Etapa | Recompensa nativa media | Rachas sin progreso | Pruebas con alguna racha |", "| --- | ---: | ---: | ---: |"]
    for stage in complete:
        content.append(f"| {cell(stage.get('label', stage['id']))} | {number(stage['mean_reward'], 1)} | {stage['stalls']} | {stage['stall_trials']}/{stage['count']} |")
    content += ["", "## Cómo se midió", "",
        f"Semillas previstas: **{', '.join(str(seed) for seed in config.get('eval_seeds', [])) or 'consultar manifiesto'}**. El muestreo se reinicia para cada prueba; las semillas cambian las acciones muestreadas en World 1-1, no el diseño del nivel. La evaluación usa pesos congelados y recompensa nativa. La configuración de aprendizaje registrada es:", "",
        "| Parámetro | Valor |", "| --- | --- |",
    ]
    for key, label in (("reward_scale", "Multiplicador de recompensa al entrenar"), ("learning_rate", "Tasa de aprendizaje"), ("target_kl", "Umbral KL objetivo"), ("ent_coef", "Coeficiente de entropía"), ("training_seed", "Semilla de entrenamiento"), ("chunk_seconds", "Segundos previstos por etapa")):
        if key in config:
            content.append(f"| {label} | `{cell(config[key])}` |")
    protocol = complete[0]["evaluation"]["protocol"] if complete else {}
    threshold = protocol.get("stall_threshold_decisions")
    deterministic = protocol.get("deterministic")
    mode = "determinista (acción preferida)" if deterministic is True else "estocástico (acciones muestreadas)" if deterministic is False else "consultar el protocolo"
    content += ["", f"Modo de evaluación: **{mode}**. Límite por intento: **{number(protocol.get('max_decisions'))} decisiones**. Una racha se registra al pasar **{number(threshold)} decisiones sin aumentar el máximo x previo**, según el protocolo. Puede incluir saltos o movimiento dentro de una zona ya recorrida; no detecta automáticamente paredes ni la causa de una muerte.", "",
        "Se muestran todas las etapas registradas, incluidas las regresiones. Los promedios excluyen evaluaciones incompletas o con protocolo distinto. Un intento parcial, si existe, queda documentado en su JSON. Si se eligió una etapa para demostrarla, esa selección se etiqueta y no sustituye la última etapa.", "",
        "Los clips son extractos del comienzo y del final de cada prueba grabada; pueden solaparse en episodios cortos. No todas las semillas necesitan tener video: cada fila conserva su traza y las métricas. Las duraciones y los límites de captura exactos están en `evaluation.json`.", "",
        "## Etapas y evidencia", "",
    ]
    for stage in stages:
        content += [f"### {cell(stage.get('label', stage['id']))}", "", f"Etapa `{cell(stage['id'])}` · {number(stage['minutes'], 1)} minutos adicionales · {number(stage.get('training_timesteps'))} decisiones acumuladas.", ""]
        if stage.get("selected_for_demo"):
            content += ["**Marcada para la demostración.** Fue seleccionada entre las etapas observadas; no es una evaluación independiente.", ""]
        if stage["warning"]:
            content += [f"**Atención:** {stage['warning']}", ""]
        if stage["evaluation"] is None:
            continue
        evidence_links = [link("Evaluación completa en JSON", stage["evaluation_file"], document)]
        if stage.get("training_summary_path"):
            summary_path = within(repo, stage["training_summary_path"])
            if summary_path.is_file():
                evidence_links.append(link("Resumen del entrenamiento", summary_path, document))
        content += [" · ".join(evidence_links), "", "| Semilla | Máx. x | Última x | Recompensa nativa | Final del intento | Rachas | Mayor racha (decisiones) | Evidencia |", "| ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |"]
        for episode in stage["episodes"]:
            evidence = []
            for key, label in (("beginning", "comienzo"), ("ending", "tramo final")):
                asset = evaluation_asset(repo, stage, episode.get("media", {}).get(key, {}).get("path"))
                if asset:
                    evidence.append(link(label, asset, document))
            trace = evaluation_asset(repo, stage, episode.get("trace_csv"))
            if trace:
                evidence.append(link("traza CSV", trace, document))
            terminal = evaluation_asset(repo, stage, episode.get("media", {}).get("terminal_frame"))
            if terminal:
                evidence.append(link("último fotograma", terminal, document))
            reason = END_REASONS.get(episode.get("end_reason"), cell(episode.get("end_reason", "sin clasificar")))
            content.append(f"| {episode['seed']} | {number(episode['max_x'])} | {number(episode.get('last_x'))} | {number(episode['native_reward'], 1)} | {reason} | {len(episode.get('stall_events', []))} | {number(episode.get('longest_no_progress_decisions'))} | {' · '.join(evidence) or 'sin archivos de muestra'} |")
        # Keep the same predeclared seed visible across all stages; link all others.
        seed_order = config.get("eval_seeds", [])
        fixed_seed = seed_order[0] if seed_order else None
        displayed = next((episode for episode in stage["episodes"] if episode["seed"] == fixed_seed), None)
        if displayed:
            columns = []
            for key, label in (("beginning", "Comienzo"), ("ending", "Tramo final")):
                metadata = displayed.get("media", {}).get(key, {})
                asset = evaluation_asset(repo, stage, metadata.get("path"))
                if asset:
                    caption = f"{label}, semilla {fixed_seed}, decisiones {metadata.get('first_decision', '?')}–{metadata.get('last_decision', '?')}"
                    columns.append((caption, link(caption, asset, document, image=True)))
            if len(columns) == 2:
                content += ["", f"| {columns[0][0]} | {columns[1][0]} |", "| --- | --- |", f"| {columns[0][1]} | {columns[1][1]} |"]
        content += ["", "**Para discutir:** ¿qué se observa al terminar este intento? ¿Qué evidencia distingue un salto tardío, una repetición de acciones o un límite de decisiones? La causa específica requiere revisar los clips; la posición por sí sola no la identifica.", ""]
    if manifest.get("final_audit_path"):
        audit_file = within(repo, manifest["final_audit_path"])
        if audit_file.is_file():
            audit = read_json(audit_file)
            audit_stage = {"evaluation_file": audit_file}
            audit_episodes = audit.get("episodes", [])
            content += ["## Prueba final con semillas nuevas", "", "Estas semillas se reservaron para el modelo final; no se mezclan con la curva de cinco pruebas repetidas ni se usan para elegir una etapa. Siguen siendo intentos del mismo World 1-1.", "", link("Datos de la prueba final", audit_file, document), ""]
            planned = audit.get("protocol", {}).get("seeds", [])
            if audit.get("status") == "complete" and planned and [ep["seed"] for ep in audit_episodes] == planned:
                values = [float(ep["max_x"]) for ep in audit_episodes]
                clears = sum(bool(ep["completed"]) for ep in audit_episodes)
                content += [f"Posición máxima media: **{number(statistics.mean(values), 1)} px** · Mediana: **{number(statistics.median(values), 1)} px** · Bandera: **{clears}/{len(values)} pruebas**.", ""]
            else:
                content += ["**Prueba final incompleta.** Sus intentos parciales no se presentan como un resultado agregado comparable.", ""]
            content += ["| Semilla | Máx. x | Bandera | Evidencia |", "| ---: | ---: | ---: | --- |"]
            for episode in audit_episodes:
                evidence = []
                for key, label in (("beginning", "comienzo"), ("ending", "tramo final")):
                    asset = evaluation_asset(repo, audit_stage, episode.get("media", {}).get(key, {}).get("path"))
                    if asset:
                        evidence.append(link(label, asset, document))
                trace = evaluation_asset(repo, audit_stage, episode.get("trace_csv"))
                if trace:
                    evidence.append(link("traza CSV", trace, document))
                content.append(f"| {episode['seed']} | {number(episode['max_x'])} | {'sí' if episode['completed'] else 'no'} | {' · '.join(evidence) or 'consultar JSON'} |")
            content.append("")
    content += ["## Material conservado y próximas sesiones", ""]
    release_url = manifest.get("model_release_url")
    if release_url:
        if not str(release_url).startswith("https://github.com/"):
            raise ValueError("model_release_url must be a GitHub HTTPS release URL")
        content += [f"Los checkpoints publicados se descargan desde la [versión de modelos de esta sesión]({release_url}). Son archivos separados del historial de código y requieren los permisos del repositorio. El enlace se incorpora al manifiesto después de confirmar la subida; consultar allí los archivos efectivamente publicados.", ""]
    else:
        content += ["Los checkpoints `.zip` se guardan localmente; todavía no hay una publicación de pesos confirmada en este manifiesto. Descargar el código de GitHub no incluye esos modelos. El manifiesto registra sus rutas para quien tenga esa copia local.", ""]
    content += ["El repositorio conserva los reportes, las métricas y las muestras publicadas. Los logs detallados permanecen locales.", ""]
    if manifest.get("latest_checkpoint"):
        content += [f"Último checkpoint local registrado: `{cell(manifest['latest_checkpoint'])}`.", ""]
    if manifest.get("pending_stage"):
        content += [f"Etapa aún sin evaluación completa: `{cell(manifest['pending_stage'])}`. Sus pesos pueden existir aunque todavía no haya métricas comparables.", ""]
    content += [
        link("Informe de esta sesión", session / "INFORME.md", document) + " · " + existing_link("Guía docente", guide, document), "",
    ]
    archives = sorted((repo / "results").glob("teaching_*/INFORME.md"))
    if archives:
        content += ["Sesiones conservadas:", ""]
        content += ["- " + link(path.parent.name, path, document) for path in archives]
        content.append("")
    if manifest.get("completion_reason"):
        content += [f"Motivo de cierre registrado: `{cell(manifest['completion_reason'])}`.", ""]
    content += ["Para actualizar el mismo panel después de generar nuevas evaluaciones:", "", "```sh", f".venv/bin/python lesson_report.py --manifest {manifest_path.relative_to(repo).as_posix()} --repo-root .", "```", "", "La actualización del panel es local hasta que se confirma y se sube a GitHub. No ejecuta aprendizaje ni modifica los pesos del modelo.", ""]
    return "\n".join(content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output-dir", type=Path, default=Path("docs/aula"))
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    manifest_path = within(repo, args.manifest)
    manifest = read_json(manifest_path)
    if not manifest.get("session_id") or not manifest.get("session_dir"):
        parser.error("manifest must include session_id and session_dir")
    session = within(repo, manifest["session_dir"])
    output = within(repo, args.output_dir)
    session.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    stages = load_stages(repo, manifest)
    chart = session / "progress.png"
    draw_chart(stages, chart, str(manifest["session_id"]))
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    archive = session / "INFORME.md"
    # Create the current archive before discovering the session list.
    archive.touch(exist_ok=True)
    for document in (archive, output / "README.md"):
        contents = make_report(repo, manifest_path, manifest, stages, document, chart, generated_at)
        temporary = document.with_suffix(document.suffix + ".tmp")
        temporary.write_text(contents, encoding="utf-8")
        temporary.replace(document)
    summary = {"session_id": manifest["session_id"], "stages": len(stages), "comparable_stages": sum(s["comparable"] for s in stages), "index": str(output / "README.md"), "archive": str(archive), "chart": str(chart)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
