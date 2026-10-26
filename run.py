"""Launch SafeSense AI locally; create an isolated environment on first run."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import threading
import webbrowser

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--inside',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if sys.version_info<(3,11): raise RuntimeError('Python 3.11 or newer is required.')
    os.chdir(ROOT)
    if not args.inside and sys.prefix==sys.base_prefix:
        target=ROOT/'.venv'
        executable=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        if not executable.exists():
            print('Creating the SafeSense AI environment…',flush=True)
            subprocess.check_call([sys.executable,'-m','venv',str(target)])
        command=[str(executable),str(ROOT/'run.py'),'--inside','--port',str(args.port)]
        if args.no_browser: command.append('--no-browser')
        return subprocess.call(command)
    os.environ.setdefault('YOLO_CONFIG_DIR',str(ROOT/'data/ultralytics'))
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'data/matplotlib'))
    (ROOT/'data').mkdir(exist_ok=True)
    if not all(importlib.util.find_spec(name) for name in ('fastapi','uvicorn','cv2','ultralytics','sqlalchemy','pydantic_settings')):
        print('Installing dependencies. Internet is needed for this first run…',flush=True)
        if not importlib.util.find_spec('torch'):
            subprocess.check_call([sys.executable,'-m','pip','install','torch','torchvision','--index-url','https://download.pytorch.org/whl/cpu'])
        subprocess.check_call([sys.executable,'-m','pip','install','-r',str(ROOT/'requirements-ai.txt')])
    env=ROOT/'.env'
    if not env.exists(): env.write_text((ROOT/'.env.example').read_text())
    if not all((ROOT/'models'/name).exists() for name in ['yolo26n.pt','ppe-yolo11n.pt','fire-yolov8s.pt']):
        subprocess.check_call([sys.executable,str(ROOT/'scripts/setup_models.py')])
    print(f'\nSafeSense AI → http://127.0.0.1:{args.port}\nLogin: admin / admin (unless changed in .env)\nPress Ctrl+C to stop.\n',flush=True)
    if not args.no_browser:
        def open_when_ready():
            import time
            import urllib.request
            for _ in range(90):
                try:
                    urllib.request.urlopen(f'http://127.0.0.1:{args.port}/api/health',timeout=1).close()
                    webbrowser.open(f'http://127.0.0.1:{args.port}');return
                except Exception: time.sleep(1)
        threading.Thread(target=open_when_ready,daemon=True).start()
    import uvicorn
    from app.main import create_app
    uvicorn.run(create_app(),host='127.0.0.1',port=args.port,access_log=False)
    return 0

if __name__=='__main__':
    try: sys.exit(main())
    except KeyboardInterrupt: pass
    except Exception as error:
        print('\nSafeSense could not start:',error,file=sys.stderr)
        print('Check your internet connection for installation, or see README.md.',file=sys.stderr)
        sys.exit(1)
