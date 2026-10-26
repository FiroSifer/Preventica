import math
import cv2
import numpy as np

_contact=None

def synthetic(t,camera_id=1):
    global _contact
    if _contact is None:
        from pathlib import Path
        _contact=cv2.imread(str(Path(__file__).resolve().parents[2]/'frontend/assets/facility.png'))
    if _contact is not None:
        h,w=_contact.shape[:2]; idx=(camera_id-1)%6; row,col=divmod(idx,3)
        tile=_contact[row*h//2:(row+1)*h//2,col*w//3:(col+1)*w//3]
        th,tw=tile.shape[:2]; crop_h=int(tw*9/16); top=max(0,(th-crop_h)//2)
        frame=cv2.resize(tile[top:top+crop_h],(800,450)).copy()
    else:
        frame=np.full((450,800,3),(38,35,42),dtype=np.uint8)
    t+=camera_id*1.3
    x=.5+.28*math.sin(t*.25); box=[x-.035,.43,x+.035,.8]
    a,b,c,d=[int(v*s) for v,s in zip(box,[800,450,800,450])]
    cv2.putText(frame,'SIMULATED VIDEO / DETECTIONS',(20,34),cv2.FONT_HERSHEY_SIMPLEX,.38,(225,210,240),1)
    cv2.putText(frame,f'SCENARIO {camera_id:02d} / {t:06.1f}s',(20,52),cv2.FONT_HERSHEY_SIMPLEX,.3,(200,190,210),1)
    return frame,[{'class_id':0,'label':'person','confidence':.95,'bbox':box,'simulated':True}]


def probe(source_type,source,settings):
    """Verify that an actual frame is available before committing a new source."""
    import os
    if source.startswith('env:'):
        source=settings.source_variable(source[4:])
        if not source: return 'The camera environment variable is not configured. Add it to .env and restart.'
    cap=None
    try:
        os.environ.setdefault('OPENCV_FFMPEG_LOGLEVEL','-8')
        cap=(cv2.VideoCapture(int(source)) if source_type=='usb' else cv2.VideoCapture(source,cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,3000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,3000]))
        ok,frame=cap.read()
        if not ok or frame is None:
            return ('USB camera not found or in use. Check the device number and camera permissions.' if source_type=='usb' else 'Cannot connect to the camera URL. Check the address, credentials and network connection.')
    except Exception:
        return 'Camera connection failed. Check the source and try again.'
    finally:
        if cap is not None: cap.release()
    return None
