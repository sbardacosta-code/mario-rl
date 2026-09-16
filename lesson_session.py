#!/usr/bin/env python3
"""Run a bounded, resumable-by-checkpoint Mario classroom training session."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone, timedelta
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


def utc():
    return datetime.now(timezone.utc)


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def run_command(command, cwd, log, timeout, stop_file=None):
    """Enforce a timeout and graceful interrupt while retaining subprocess logs."""
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('a') as output:
        process = subprocess.Popen(command, cwd=cwd, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        end = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if time.monotonic() >= end or (stop_file and stop_file.exists()):
                    os.killpg(process.pid, signal.SIGINT)
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    return process.returncode, 'stop_requested' if stop_file and stop_file.exists() else 'command_timeout'
                time.sleep(0.5)
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            raise
        return process.returncode, None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--initial-model', type=Path, default=Path('results/reward_scaled/checkpoints/final.zip'))
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--start-prepared', action='store_true')
    parser.add_argument('--max-seconds', type=float, default=10800)
    parser.add_argument('--chunk-seconds', type=float, default=900)
    parser.add_argument('--max-chunks', type=int, default=100)
    parser.add_argument('--eval-seconds', type=float, default=180)
    parser.add_argument('--eval-max-decisions', type=int, default=3000)
    parser.add_argument('--eval-seeds', type=int, nargs='+', default=[101,202,303,404,505])
    parser.add_argument('--video-seeds', type=int, nargs='+', default=[101,202,303])
    parser.add_argument('--publish', action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    run=(root/args.run_dir).resolve()
    if not run.is_relative_to(root/'results'):
        parser.error('--run-dir must be inside this repository results directory')
    if args.prepare_only and args.start_prepared:
        parser.error('choose one preparation mode')
    if not all(math.isfinite(x) and x>0 for x in [args.max_seconds,args.chunk_seconds,args.eval_seconds]) or args.max_seconds>10800:
        parser.error('budgets must be positive and session maximum is 10800 seconds')
    if args.max_chunks<1 or args.eval_max_decisions<1:
        parser.error('counts must be positive')
    run.mkdir(parents=True,exist_ok=True)
    lock=(root/'.cache').resolve(); lock.mkdir(exist_ok=True)
    with (lock/'lesson_session.lock').open('w') as lock_file:
        try: fcntl.flock(lock_file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: parser.error('another classroom session is already running')
        return session(args,root,run)


def session(args,root,run):
    py=sys.executable
    manifest_path=run/'manifest.json'
    rel=lambda p: str(Path(p).resolve().relative_to(root))
    def command(command, log, timeout=180, stop=False):
        code, reason=run_command(command,root,run/'logs'/log,timeout,run/'STOP' if stop else None)
        if code!=0 and reason!='stop_requested':
            raise RuntimeError(f'{Path(command[1]).name}: return code {code}; {reason or "see log"} ({log})')
        return reason
    def render():
        command([py,'lesson_report.py','--manifest',rel(manifest_path)],'report.log',120)
    def publish():
        if not args.publish: return
        paths=[rel(run),'docs/aula']
        try:
            branch=subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip()
            if branch!='main': raise RuntimeError('La publicación automática requiere la rama main; no se cambian ramas.')
            subprocess.run(['git','add','--',*paths],cwd=root,check=True,capture_output=True,text=True,timeout=30)
            staged=subprocess.run(['git','diff','--cached','--name-only'],cwd=root,check=True,capture_output=True,text=True,timeout=30).stdout.splitlines()
            if any(not(name.startswith(rel(run)+'/') or name.startswith('docs/aula/')) for name in staged):
                raise RuntimeError('Hay otros cambios preparados en Git; se conservan sin incluirlos en el commit automático.')
            if staged:
                subprocess.run(['git','diff','--cached','--check'],cwd=root,check=True,capture_output=True,text=True,timeout=30)
                subprocess.run(['git','commit','-m',f'Update classroom session {manifest["session_id"]}: {len(manifest["stages"])} stages ({manifest["status"]})'],cwd=root,check=True,capture_output=True,text=True,timeout=60)
            subprocess.run(['git','push','origin','main'],cwd=root,check=True,capture_output=True,text=True,timeout=60)
            save(run/'logs/publication.json',{'status':'published','at':utc().isoformat(),'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()})
        except (subprocess.SubprocessError,RuntimeError) as error:
            save(run/'logs/publication.json',{'status':'pending','at':utc().isoformat(),'error':str(error)})
            print('Publicación pendiente:',error,flush=True)
    def evaluate(model, stage_path, seeds=None, videos=None, budget=None):
        stage_path.parent.mkdir(parents=True,exist_ok=True)
        seeds=args.eval_seeds if seeds is None else seeds
        videos=args.video_seeds if videos is None else videos
        cmd=[py,'lesson_eval.py','--model',rel(model),'--output-dir',rel(stage_path),'--seeds',*map(str,seeds),'--max-decisions',str(args.eval_max_decisions),'--max-seconds',str(budget or args.eval_seconds),'--video-seeds',*map(str,videos)]
        command(cmd,stage_path.name+'.log',min((budget or args.eval_seconds)+25,240))
        evaluation=json.loads((stage_path/'evaluation.json').read_text())
        if evaluation['status']!='complete':
            raise RuntimeError('La evaluación quedó incompleta; no se presenta como una etapa comparable.')
        return evaluation
    if args.start_prepared:
        manifest=json.loads(manifest_path.read_text())
        if manifest['status']!='prepared': raise RuntimeError('Only a prepared session can be started; choose a new directory to continue a finished session.')
        for name, digest in manifest['source_hashes'].items():
            if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
                raise RuntimeError(f'El código cambió desde la preparación: {name}')
        # The prepared experiment is immutable: do not silently change its settings.
        for key in ['max_seconds','chunk_seconds','max_chunks','eval_seconds','eval_max_decisions','eval_seeds','video_seeds']:
            setattr(args,key,manifest['session_args'][key])
        model=root/manifest['initial_checkpoint']
        if hashlib.sha256(model.read_bytes()).hexdigest()!=manifest['initial_checkpoint_sha256']:
            raise RuntimeError('The initial checkpoint changed after preparation')
    else:
        if manifest_path.exists() or (run/'stages').exists(): raise RuntimeError('Existing experiments are never overwritten; use a new run directory.')
        model=(root/args.initial_model).resolve()
        if not model.is_relative_to(root): raise RuntimeError('Initial model must be in this repository')
        import torch
        from stable_baselines3 import PPO
        torch.set_num_threads(1)
        loaded=PPO.load(model,device='cpu'); initial_steps=loaded.num_timesteps
        del loaded
        manifest={
            'session_id':run.name,'session_dir':rel(run),'status':'preparing','created_at':utc().isoformat(),
            'started_at':None,'deadline_utc':None,'pid':os.getpid(),
            'initial_checkpoint':rel(model),'initial_checkpoint_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),
            'configuration':{'reward_scale':0.01,'learning_rate':0.0001,'target_kl':0.02,'ent_coef':0.01,'training_seed':123,'eval_seeds':args.eval_seeds,'chunk_seconds':args.chunk_seconds,'device':'cpu','threads':1,'n_envs':4},
            'session_args':{key:getattr(args,key) for key in ['max_seconds','chunk_seconds','max_chunks','eval_seconds','eval_max_decisions','eval_seeds','video_seeds']},
            'stages':[],'elapsed_training_seconds':0,'completion_reason':None,
            'interpretation':'Continúa un modelo previo; cambia tasa de aprendizaje y límite KL juntos. No permite atribuir una diferencia a un solo parámetro. Cinco semillas de acciones son una muestra pequeña del mismo nivel.',
            'source_hashes':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['train.py','mario_env.py','lesson_eval.py','lesson_report.py','lesson_session.py','publish_lesson_models.py','requirements-lock.txt']}}
        save(manifest_path,manifest)
        baseline=run/'stages/00_baseline'
        evaluate(model,baseline)
        manifest['stages'].append({'id':'00_baseline','label':f'Inicio: modelo con {initial_steps:,} decisiones previas','elapsed_training_seconds':0,'training_timesteps':initial_steps,'evaluation_path':rel(baseline/'evaluation.json'),'checkpoint_path':rel(model),'training_summary_path':None})
        manifest['status']='prepared'; save(manifest_path,manifest); render()
        if args.prepare_only:
            print(json.dumps({'status':'prepared','manifest':rel(manifest_path)},ensure_ascii=False),flush=True)
            return 0
    start=utc(); deadline=start+timedelta(seconds=args.max_seconds)
    manifest.update(status='running',started_at=start.isoformat(),deadline_utc=deadline.isoformat(),pid=os.getpid())
    save(manifest_path,manifest); render(); publish()
    keep_awake=None
    if sys.platform=='darwin' and shutil.which('caffeinate'):
        keep_awake=subprocess.Popen(['caffeinate','-i','-w',str(os.getpid())])
    reason='session_time_budget_reached'
    reserve=min(900,args.max_seconds/3)  # Keep time for stage evaluation, final audit, reporting, and publication.
    try:
        for index in range(1,args.max_chunks+1):
            remaining=(deadline-utc()).total_seconds()
            if (run/'STOP').exists(): reason='stop_requested'; break
            budget=min(args.chunk_seconds,remaining-reserve)
            if budget<min(60,args.chunk_seconds): break
            stage_id=f'{index:02d}_stage'
            training=run/'training'/stage_id
            for name,digest in manifest['source_hashes'].items():
                if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
                    raise RuntimeError(f'El código cambió durante la sesión: {name}')
            manifest['active_stage']=stage_id; manifest['active_training_dir']=rel(training)
            save(manifest_path,manifest)
            stop=command([py,'train.py','--run-dir',rel(training),'--resume',rel(model),'--reward-scale','0.01','--learning-rate','0.0001','--target-kl','0.02','--ent-coef','0.01','--device','cpu','--threads','1','--n-envs','4','--seed','123','--max-seconds',str(budget),'--deadline-utc',(deadline-timedelta(seconds=reserve)).isoformat(),'--archive-seconds','0'],stage_id+'_training.log',min(budget+60,remaining-30),True)
            summary=json.loads((training/'training_summary.json').read_text())
            if stop=='stop_requested' and summary['optimizer_steps_this_run']==0:
                reason='stop_requested'; break
            if summary['status'] not in ['completed','interrupted'] or not summary['all_parameters_finite'] or summary['optimizer_steps_this_run']<=0:
                raise RuntimeError('El tramo no produjo actualizaciones finitas verificables.')
            model=training/'checkpoints/final.zip'
            manifest['elapsed_training_seconds']+=summary['elapsed_seconds']
            manifest['latest_checkpoint']=rel(model)
            manifest['latest_checkpoint_sha256']=hashlib.sha256(model.read_bytes()).hexdigest()
            manifest['pending_stage']={'id':stage_id,'training_summary_path':rel(training/'training_summary.json'),'checkpoint_path':rel(model),'status':'evaluation_pending'}
            save(manifest_path,manifest)
            stage=run/'stages'/stage_id
            evaluate(model,stage,budget=max(1,min(args.eval_seconds,(deadline-utc()).total_seconds()-30)))
            shutil.copy2(training/'logs/progress.csv',training/'learning_metrics.csv')
            manifest['stages'].append({'id':stage_id,'label':f'Etapa {index}: {manifest["elapsed_training_seconds"]/60:.0f} min adicionales','elapsed_training_seconds':manifest['elapsed_training_seconds'],'training_timesteps':summary['timesteps'],'evaluation_path':rel(stage/'evaluation.json'),'checkpoint_path':rel(model),'training_summary_path':rel(training/'training_summary.json'),'checkpoint_sha256':hashlib.sha256(model.read_bytes()).hexdigest()})
            manifest['latest_checkpoint']=rel(model); manifest['active_stage']=None
            manifest.pop('pending_stage',None)
            save(manifest_path,manifest); render(); publish()
            print(json.dumps({'stage':stage_id,'training_minutes':manifest['elapsed_training_seconds']/60,'timesteps':summary['timesteps']},ensure_ascii=False),flush=True)
            if stop: reason=stop; break
        else: reason='stage_limit_reached'
        if not (run/'STOP').exists() and len(manifest['stages'])>1 and (deadline-utc()).total_seconds()>30:
            # New seeds, never used to select a checkpoint; use the final budget-selected model.
            audit=run/'final_audit'
            evaluate(model,audit,seeds=list(range(1001,1011)),videos=[1001],budget=min(args.eval_seconds,(deadline-utc()).total_seconds()-20))
            manifest['final_audit_path']=rel(audit/'evaluation.json')
        manifest.update(status='completed',completion_reason=reason,finished_at=utc().isoformat(),latest_checkpoint=rel(model),active_stage=None)
    except KeyboardInterrupt:
        manifest.update(status='interrupted',completion_reason='keyboard_interrupt',finished_at=utc().isoformat())
    except Exception as error:
        manifest.update(status='failed',completion_reason=str(error),finished_at=utc().isoformat())
        import traceback; traceback.print_exc()
    finally:
        if keep_awake: keep_awake.terminate()
        manifest['wall_seconds']=(utc()-start).total_seconds()
        save(manifest_path,manifest)
        if args.publish and manifest['status']=='completed':
            try:
                # Upload model snapshots separately from Git history. A retry can finish publication without training.
                command([py,'publish_lesson_models.py','--manifest',rel(manifest_path),'--max-seconds',str(max(1,min(480,(deadline-utc()).total_seconds()-30)))],'models_publication.log',max(5,min(500,(deadline-utc()).total_seconds()-10)))
                manifest.update(json.loads(manifest_path.read_text()))
            except Exception as error:
                manifest['model_release_status']='pending'
                manifest['model_release_error']=str(error)
                save(manifest_path,manifest)
        try:
            render(); publish()
        except Exception as error: print('Final report error:',error,flush=True)
    print(json.dumps({'status':manifest['status'],'reason':manifest['completion_reason'],'manifest':rel(manifest_path)},ensure_ascii=False),flush=True)
    return 0 if manifest['status']=='completed' else 1


if __name__=='__main__':
    raise SystemExit(main())
