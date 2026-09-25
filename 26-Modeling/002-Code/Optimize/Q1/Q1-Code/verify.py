"""Independent numerical and combinatorial cross-checks for Q1."""
from model import *
import json
from scipy.optimize import brentq
R=Path(__file__).resolve().parent/'results'
geo=[]
for r in areas.itertuples():
    x0,y0=to_pix(LON_O,LAT_O);x1,y1=to_pix(r.lon,r.lat)
    ts=[0.,1.]
    for a,b in [(x0,x1),(y0,y1)]:
        if b!=a:ts += [(k-a)/(b-a) for k in range(math.floor(min(a,b))+1,math.ceil(max(a,b))) if 0<(k-a)/(b-a)<1]
    ts=sorted(set(ts));mids=(np.array(ts[:-1])+np.array(ts[1:]))/2
    cells={(math.floor(y0+t*(y1-y0)),math.floor(x0+t*(x1-x0))) for t in mids}
    cells|={(math.floor(y0),math.floor(x0)),(math.floor(y1),math.floor(x1))}
    zz=np.array([DEM[y,x] for y,x in cells]);assert np.isfinite(zz).all()
    assert abs(zz.max()-SEG[r.id]['zmax'])<1e-8
    geo.append(dict(area=r.id,cells=len(cells),height=float(zz.max()),passed=True))
roots=[]
for a in AREA_IDS:
 for g in TYPES:
    p=uav.loc[g];z=SEG[a];budget=(1-p.rho)*p.E_use
    root=p.Q if sortie_energy(p,z,p.Q)<=budget else brentq(lambda q:sortie_energy(p,z,q)-budget,0,p.Q)
    assert abs(root-QMAX.loc[a,g])<1e-8
    roots.append(dict(area=a,g=g,qmax=root,error=root-QMAX.loc[a,g]))
# Quadratic dominance test, independent of the prefix-minimum implementation.
def naive(cands):
    arr=np.unique(np.round(np.array([c[:3] for c in cands]),8),axis=0)
    keep=[]
    for c in arr:
        if not np.any(np.all(arr<=c+1e-8,axis=1)&np.any(arr<c-1e-8,axis=1)):keep.append(c)
    return np.array(keep).reshape(-1,3)
sol=solve_all(QMAX);states=0
for s in sol.values():
 for r,front in s.memo.items():
    if not any(r):continue
    cand=[]
    for pt in s.pats:
        if all(n<=ri for n,ri in zip(pt['n'],r)):
            child=tuple(ri-n for n,ri in zip(pt['n'],r))
            cand.extend([(c[0]+1,c[1]+pt['E'],c[2]+pt['T']) for c in s.memo[child]])
    expected=naive(cand);actual=np.array([c[:3] for c in front]).reshape(-1,3)
    assert len(expected)==len(actual)
    assert all(np.any(np.all(np.isclose(actual,c,atol=2e-8,rtol=0),axis=1)) for c in expected)
    states+=1
pd.DataFrame(geo).to_csv(R/'geometry_checks.csv',index=False)
pd.DataFrame(roots).to_csv(R/'payload_root_checks.csv',index=False)
result={'geometry_routes_checked':len(geo),'payload_roots_checked':len(roots),'DP_states_checked_against_quadratic_dominance':states,'status':'passed'}
(R/'verification.json').write_text(json.dumps(result,indent=2));print(result)
