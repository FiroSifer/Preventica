"""Download and verify the three pretrained detectors listed in models/catalog.json."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--people-only',action='store_true',help='Download just official YOLO26 nano')
    args=parser.parse_args()
    os.environ.setdefault('YOLO_CONFIG_DIR',str(ROOT/'data'/'ultralytics'))
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'data'/'matplotlib'))
    import requests
    import numpy as np
    from ultralytics import YOLO
    catalog=json.loads((ROOT/'models/catalog.json').read_text())
    values={}
    for entry in catalog:
        if args.people_only and entry['kind']!='people': continue
        target=ROOT/'models'/entry['file']
        expected=entry['sha256']
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=expected:
            print('Downloading',entry['kind'],'from',entry['source'])
            partial=target.with_suffix('.partial')
            try:
                with requests.get(entry['download_url'],stream=True,timeout=(15,120)) as response:
                    response.raise_for_status()
                    with partial.open('wb') as out:
                        for chunk in response.iter_content(1024*1024): out.write(chunk)
                if hashlib.sha256(partial.read_bytes()).hexdigest()!=expected: raise ValueError('Checksum mismatch. Model source changed; review the catalog before using new weights.')
                partial.replace(target)
            finally:
                partial.unlink(missing_ok=True)
        model=YOLO(str(target),task='detect')
        model.predict(np.zeros((320,320,3),dtype=np.uint8),device='cpu',verbose=False)
        print('Verified',entry['kind'],':',', '.join(model.names.values()))
        key={'people':'SAFESENSE_MODEL_PATH','ppe':'SAFESENSE_PPE_MODEL_PATH','fire':'SAFESENSE_FIRE_MODEL_PATH'}[entry['kind']]
        values[key]='models/'+entry['file']
    env=ROOT/'.env'
    content=env.read_text() if env.exists() else (ROOT/'.env.example').read_text()
    lines=[line for line in content.splitlines() if not any(line.startswith(k+'=') for k in values)]
    lines += [key+'='+value for key,value in values.items()]
    temp=env.with_name('.env.tmp'); temp.write_text('\n'.join(lines)+'\n');temp.replace(env)
    print('Model setup complete. Restart SafeSense AI.')

if __name__=='__main__':
    try: main()
    except Exception as exc: print('Model setup failed:',exc,file=sys.stderr);sys.exit(1)
