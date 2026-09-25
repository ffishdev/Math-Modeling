"""Reproduce Q1 results, time-first decisions and independent checks."""
from model import *
import json, hashlib, platform, time
from scipy.optimize import milp, Bounds, LinearConstraint
OUT=Path(__file__).resolve().parent/'results'; OUT.mkdir(exist_ok=True)
t0=time.time()
def dump(name,obj):
    def conv(x):
        if isinstance(x,np.generic): return x.item()
        if isinstance(x,np.ndarray): return x.tolist()
        raise TypeError(type(x))
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=conv,allow_nan=False))
def csv(name,df): df.to_csv(OUT/name,index=True,encoding='utf-8-sig')
SOL=solve_all(QMAX); fronts=[s.front for s in SOL.values()]; GF=global_front(fronts)
ideal=np.min(np.array([c[:3] for c in GF]),axis=0)
RULES={'R1':'NET','R2':'ENT','R3':'TNE','R4':'W'}
plans={}; rows=[]
for label,rule in RULES.items():
    plans[label]=[r for a,s in SOL.items() for r in s.reconstruct(pick(s.front,rule,ideal),QMAX)]
    plan=plans[label]; totals=[len(plan),sum(r['E'] for r in plan),sum(r['T'] for r in plan)]
    rows.append(dict(rule=label,N=totals[0],E=totals[1],T_h=totals[2]/3600,**{g:sum(r['g']==g for r in plan) for g in TYPES}))
csv('rules.csv',pd.DataFrame(rows).set_index('rule'))
csv('qmax.csv',QMAX);csv('binding.csv',QBIND);csv('geometry.csv',seg_df);csv('boxes.csv',boxes);csv('uav.csv',uav)
csv('front.csv',pd.DataFrame([c[:3] for c in GF],columns=['N','E','T_s']))
dump('plans.json',plans)
for key,plan in plans.items():
    flat=[{k:v for k,v in r.items() if k not in ['n','E_parts','boxes']}|{'nbox':r['n'],'boxes':','.join(r['boxes'])} for r in plan]
    csv(f'plan_{key}.csv',pd.DataFrame(flat))
policy=[]
for label,allowed in {'A':['A'],'B':['B'],'C':['C'],'A+B':['A','B'],'A+B+C':TYPES}.items():
    ss=solve_all(QMAX,allowed); chosen=[pick(s.front,'TNE') for s in ss.values()]
    missing=[a for a,s in ss.items() if not s.front]; complete=not missing
    policy.append(dict(policy=label,complete=complete,missing=','.join(missing),N=sum(c[0] for c in chosen) if complete else None,E=sum(c[1] for c in chosen) if complete else None,T_h=sum(c[2] for c in chosen)/3600 if complete else None))
csv('policies.csv',pd.DataFrame(policy).set_index('policy'))
# Independent raw-pattern integer-program validation; no DP pattern pruning.
checks=[]
for a in AREA_IDS:
    s=SOL[a]; patterns=[]
    for g in TYPES:
        p=uav.loc[g]
        for counts in itertools.product(*(range(n+1) for n in s.r0)):
            if not any(counts): continue
            mass=np.dot(counts,s.m); vol=np.dot(counts,s.v)
            # Recompute energy directly from the appendix, without qmax.
            z=SEG[a]; energy=p.E_use*z['d']/(p.L0-(p.L0-p.LF)*(mass/p.Q)**1.5)+p.E_use*z['d']/p.L0+(p.m0+mass)*G0*z['hup_out']/(p.eta_up*3.6e6)+p.m0*G0*z['hup_ret']/(p.eta_up*3.6e6) if mass<=p.Q else math.inf
            if mass<=p.Q+1e-9 and vol<=p.V+1e-9 and energy<=(1-p.rho)*p.E_use+1e-9:
                patterns.append((counts,energy,sortie_time(p,z,sum(counts))))
    A=np.array([p[0] for p in patterns]).T;cost=np.array([[1,p[1],p[2]] for p in patterns]); base=LinearConstraint(A,s.r0,s.r0)
    for j in range(3):
        res=milp(cost[:,j],integrality=np.ones(len(patterns)),bounds=Bounds(0,np.inf),constraints=base,options={'mip_rel_gap':0})
        target=min(c[j] for c in s.front);assert res.success and abs(res.fun-target)<1e-5,(a,j,res.message,res.fun,target)
        checks.append(dict(area=a,objective=['N','E','T_s'][j],dp=target,milp=float(res.fun),gap=float(res.mip_gap)))
    # Exhaust all feasible integer N budgets: minimize E with T bounded at each DP point.
    # This supplies an independent certificate for every reported point, not only each ideal coordinate.
    for c in s.front:
        cons=[base,LinearConstraint(cost[:,0],-np.inf,c[0]),LinearConstraint(cost[:,2],-np.inf,c[2]+1e-7)]
        res=milp(cost[:,1],integrality=np.ones(len(patterns)),bounds=Bounds(0,np.inf),constraints=cons,options={'mip_rel_gap':0})
        assert res.success and abs(res.fun-c[1])<1e-5
csv('milp_checks.csv',pd.DataFrame(checks))
# Verify actual box IDs, recompute load, volume, energy and time independently.
validation=[]
for rule,plan in plans.items():
    ids=[b for r in plan for b in r['boxes']];assert len(ids)==len(set(ids))==len(boxes) and set(ids)==set(boxes.box)
    for r in plan:
        b=boxes.set_index('box').loc[r['boxes']];p=uav.loc[r['g']];z=SEG[r['area']]
        assert set(b.area)=={r['area']}
        q=b.mass.sum();v=b.vol.sum();e=p.E_use*z['d']*(1/(p.L0-(p.L0-p.LF)*(q/p.Q)**1.5)+1/p.L0)+G0*((p.m0+q)*z['hup_out']+p.m0*z['hup_ret'])/(p.eta_up*3.6e6)
        ts=(z['hup_out']+z['hup_ret'])/p.v_up+2*z['d']/p.v_c+(z['hdn_out']+z['hdn_ret'])/p.v_dn+p.t_prep+p.t_hand+len(b)*(p.t_load+p.t_box)
        assert q<=p.Q+1e-8 and v<=p.V+1e-8 and e<=(1-p.rho)*p.E_use+1e-8
        assert abs(e-r['E'])<1e-8 and abs(ts-r['T'])<1e-6 and abs(q-r['mass'])<1e-8
        validation.append(dict(rule=rule,area=r['area'],sortie=r['sortie'],mass_slack=p.Q-q,volume_slack=p.V-v,energy_slack=(1-p.rho)*p.E_use-e,return_soc=1-e/p.E_use))
csv('constraint_checks.csv',pd.DataFrame(validation))
# Exact complete-delivery reserve boundary: unlimited singleton sorties are allowed.
# Necessity and sufficiency: every box fits at least one type when flown alone.
bounds=[]
for b in boxes.itertuples():
    for g in TYPES:
        p=uav.loc[g]
        if b.mass<=p.Q and b.vol<=p.V:
            bounds.append(dict(box=b.box,area=b.area,mat=b.mat,g=g,rho_limit=1-sortie_energy(p,SEG[b.area],b.mass)/p.E_use))
bounddf=pd.DataFrame(bounds);single=bounddf.groupby('box').rho_limit.max();rho_star=float(single.min())
csv('singleton_boundaries.csv',bounddf)
critical=single[single<=rho_star+1e-10].index.tolist()
# Sweep common reserve; all global totals become missing on incomplete coverage.
sens=[];sensq=[];sensarea=[]
for rho in np.round(np.arange(.05,.451,.01),2):
    qm,_=compute_qmax({g:rho for g in TYPES});ss=solve_all(qm)
    for a in AREA_IDS:
        for g in TYPES:sensq.append(dict(rho=rho,area=a,g=g,qmax=qm.loc[a,g]))
    missing=[a for a,s in ss.items() if not s.front]
    for rule in ['TNE','NET','ENT']:
        chosen={a:pick(s.front,rule) for a,s in ss.items()}
        complete=not missing
        sens.append(dict(rho=rho,rule=rule,complete=complete,missing=','.join(missing),N=sum(c[0] for c in chosen.values()) if complete else None,E=sum(c[1] for c in chosen.values()) if complete else None,T_h=sum(c[2] for c in chosen.values())/3600 if complete else None))
        if rule=='TNE':
            for a,c in chosen.items():sensarea.append(dict(rho=rho,area=a,N=c[0] if c else None))
    print('reserve',rho,'complete',not missing,flush=True)
csv('sensitivity.csv',pd.DataFrame(sens));csv('sensitivity_payload.csv',pd.DataFrame(sensq));csv('sensitivity_area.csv',pd.DataFrame(sensarea))
for rho,feasible in [(rho_star-1e-6,True),(rho_star+1e-6,False)]:
    qm,_=compute_qmax({g:rho for g in TYPES});ss=solve_all(qm);assert all(bool(s.front) for s in ss.values())==feasible
P=np.array([c[:3] for c in GF]);pT=np.array(pick(GF,'TNE')[:3]);pE=np.array(pick(GF,'ENT')[:3]);delta=pT-pE
# wN+wE+wT=1; time plan wins when wE*positive energy regret <= wN*N regret + wT*T regret.
a=(pE[0]-pT[0])/ideal[0];b=(pT[1]-pE[1])/ideal[1];c=(pE[2]-pT[2])/ideal[2]
meta=dict(ideal=ideal,pareto_points=P,recommended_rule='R3 / TNE',rho_star=rho_star,critical_boxes=critical,delta_T_minus_E=delta,weighted_boundary=dict(aN=a,bE=b,cT=c,energy_weight_when_N_T_equal=(a+c)/(a+c+2*b)),n_boxes=len(boxes),total_mass=float(boxes.mass.sum()),total_volume=float(boxes.vol.sum()),runtime_s=time.time()-t0,python=platform.python_version(),source_notebook_sha256=hashlib.sha256((PROJECT/'26-Modeling/002-Code/Q1.ipynb').read_bytes()).hexdigest())
dump('summary.json',meta)
print(json.dumps(meta,ensure_ascii=False,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else x,indent=2))
