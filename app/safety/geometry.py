import math

def cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

def on_segment(a,b,p):
    return abs(cross(a,b,p)) < 1e-9 and min(a[0],b[0])-1e-9 <= p[0] <= max(a[0],b[0])+1e-9 and min(a[1],b[1])-1e-9 <= p[1] <= max(a[1],b[1])+1e-9

def intersects(a,b,c,d):
    return (cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0) or any((on_segment(a,b,c),on_segment(a,b,d),on_segment(c,d,a),on_segment(c,d,b)))

def validate_polygon(points):
    if not 3 <= len(points) <= 100 or any(len(p)!=2 or any(not math.isfinite(v) or not 0<=v<=1 for v in p) for p in points):
        raise ValueError('Use 3–100 finite normalized vertices within [0,1]')
    if len(set(map(tuple, points))) != len(points):
        raise ValueError('Vertices must be distinct')
    n=len(points)
    if abs(sum(points[i][0]*points[(i+1)%n][1]-points[(i+1)%n][0]*points[i][1] for i in range(n))) < 1e-7:
        raise ValueError('Polygon must have nonzero area')
    for i in range(n):
        for j in range(i+1,n):
            if j==i+1 or (i==0 and j==n-1): continue
            if intersects(points[i],points[(i+1)%n],points[j],points[(j+1)%n]):
                raise ValueError('Polygon edges must not intersect')
    return points

def inside(point, polygon):
    x,y=point; result=False
    for a,b in zip(polygon, polygon[1:]+polygon[:1]):
        if on_segment(a,b,point): return True
        if (a[1]>y)!=(b[1]>y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]: result=not result
    return result
