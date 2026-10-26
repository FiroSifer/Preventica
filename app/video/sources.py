import math
import cv2
import numpy as np

def synthetic(t):
    frame=np.zeros((450,800,3),dtype=np.uint8); frame[:]=(32,39,48)
    for x in range(0,800,80): cv2.line(frame,(x,90),(x,450),(45,55,65),1)
    for y in range(90,450,60): cv2.line(frame,(0,y),(800,y),(45,55,65),1)
    x=.5+.28*math.sin(t*.25); box=[x-.06,.32,x+.06,.82]
    a,b,c,d=[int(v*s) for v,s in zip(box,[800,450,800,450])]
    cv2.rectangle(frame,(a,b),(c,d),(160,125,50),-1); cv2.circle(frame,((a+c)//2,b+5),22,(165,174,183),-1)
    cv2.putText(frame,'SIMULATED VIDEO / DETECTIONS',(24,38),cv2.FONT_HERSHEY_SIMPLEX,.65,(70,200,255),2)
    cv2.putText(frame,f'Demo clock {t:06.1f}s',(24,68),cv2.FONT_HERSHEY_SIMPLEX,.5,(200,200,200),1)
    return frame,[{'class_id':0,'label':'person','confidence':.95,'bbox':box,'simulated':True}]
