#!/usr/bin/env python3
"""Persist classroom checkpoints as verified GitHub Release assets."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from urllib.parse import quote


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--max-seconds',type=float,default=480)
    args=parser.parse_args()
    if not math.isfinite(args.max_seconds) or args.max_seconds<=0:
        parser.error('--max-seconds must be finite and positive')
    root=Path(__file__).resolve().parent
    path=(root/args.manifest).resolve(); manifest=json.loads(path.read_text())
    if manifest['status']!='completed': raise RuntimeError('Only completed sessions are published as model releases')
    deadline=time.monotonic()+args.max_seconds
    run=root/manifest['session_dir']; exports=run/'checkpoints/exports';exports.mkdir(parents=True,exist_ok=True)
    def call(argv,check=True):
        remaining=deadline-time.monotonic()
        if remaining<1: raise TimeoutError('Model publication time budget reached; retry without training')
        return subprocess.run(argv,cwd=root,text=True,capture_output=True,check=check,timeout=min(90,remaining))
    repo=json.loads(call(['gh','repo','view','--json','nameWithOwner']).stdout)['nameWithOwner']
    tag=manifest['session_id']
    endpoint=f'repos/{repo}/releases/tags/{quote(tag,safe="")}'
    existing=call(['gh','api',endpoint],False)
    if existing.returncode:
        if '404' not in existing.stderr: raise RuntimeError(existing.stderr)
        notes=run/'logs/release_notes.md';notes.parent.mkdir(exist_ok=True)
        notes.write_text(f'Modelos de la sesión docente de Mario. Cada archivo corresponde a una etapa registrada en el manifiesto.\n\nGuía y galería: https://github.com/{repo}/tree/main/docs/aula\n\nLos resultados pueden avanzar o retroceder; los clips y las métricas incluyen todas las etapas.\n')
        call(['gh','release','create',tag,'--target','main','--title',f'Mario: {tag}','--notes-file',str(notes)])
        existing=call(['gh','api',endpoint])
    release=json.loads(existing.stdout)
    published=[]
    for stage in manifest['stages']:
        model=root/stage['checkpoint_path']; asset=exports/(stage['id']+'.zip')
        digest=hashlib.sha256(model.read_bytes()).hexdigest()
        expected=stage.get('checkpoint_sha256',manifest['initial_checkpoint_sha256'] if stage['id']=='00_baseline' else None)
        if expected and digest!=expected: raise RuntimeError('Checkpoint changed since evaluation: '+str(model))
        remote=next((item for item in release['assets'] if item['name']==asset.name),None)
        if remote is None:
            shutil.copy2(model,asset)
            call(['gh','release','upload',tag,str(asset)])
            release=json.loads(call(['gh','api',endpoint]).stdout)
            remote=next((item for item in release['assets'] if item['name']==asset.name),None)
        if remote is None or remote.get('state')!='uploaded' or remote.get('size')!=model.stat().st_size:
            raise RuntimeError(f'Asset {asset.name} is incomplete or differs in size; no existing asset was overwritten.')
        remote_digest=remote.get('digest')
        if remote_digest:
            if remote_digest!='sha256:'+digest:
                raise RuntimeError('Remote model digest mismatch: '+asset.name)
        else:
            # Older GitHub APIs may omit digests; verify bytes in a bounded download.
            with tempfile.TemporaryDirectory(dir=exports) as directory:
                call(['gh','release','download',tag,'--pattern',asset.name,'--dir',directory])
                if hashlib.sha256((Path(directory)/asset.name).read_bytes()).hexdigest()!=digest:
                    raise RuntimeError('Downloaded model digest mismatch: '+asset.name)
        published.append({'stage_id':stage['id'],'asset':asset.name,'sha256':digest,'remote_bytes_verified':True})
    manifest['model_release_url']=release['html_url']
    manifest['model_release_status']='complete'
    manifest.pop('model_release_error',None)
    manifest['published_models']=published
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n');temporary.replace(path)
    print(json.dumps({'status':'published','url':release['html_url'],'assets':len(published)},ensure_ascii=False))

if __name__=='__main__': main()
