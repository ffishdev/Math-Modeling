"""Publication figures from verified original inputs and analysis results.
All numerical panels are deterministic model outputs, not measured performance.
"""
from model import *
import json,sys,os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource, LinearSegmentedColormap
from matplotlib import font_manager
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
HERE=Path(__file__).resolve().parent;R=HERE/'results';FIG=HERE.parent/'Q1-latex/figures';QA=HERE/'qa'
FIG.mkdir(exist_ok=True);QA.mkdir(exist_ok=True)
SKILL=Path(os.environ.get('NATURE_FIGURE_SKILL',str(Path.home()/'.agents/skills/nature-figure')))
sys.path.insert(0,str(SKILL/'scripts'))
from audit_panel_alignment import require_matplotlib_panel_alignment
for fp in ['/System/Library/Fonts/Supplemental/Songti.ttc','/System/Library/Fonts/Supplemental/Arial.ttf']:
    if Path(fp).exists():font_manager.fontManager.addfont(fp)
plt.rcParams.update({'font.family':['Arial','Songti SC'],'font.size':9,'axes.labelsize':9,'axes.titlesize':10,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'pdf.fonttype':42,'svg.fonttype':'none','axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,'savefig.dpi':300,'figure.facecolor':'white','axes.labelcolor':'#253546','text.color':'#253546','xtick.color':'#4c5862','ytick.color':'#4c5862'})
COL={'A':'#639B90','B':'#416C99','C':'#C77F5B'};TC='#416C99';EC='#C77F5B';GRAY='#8c969d'
MATS={'医疗物资':'#A75962','饮用水':'#6798B7','应急食品':'#CAB36E','生活卫生用品':'#8F91AA'}
plans=json.loads((R/'plans.json').read_text());meta=json.loads((R/'summary.json').read_text())
plan=plans['R3'];W=180/25.4

def panels(axs,titles):
    for i,(ax,title) in enumerate(zip(np.ravel(axs),titles)):
        ax.set_title(title,loc='left',pad=12)
        ax.text(-.12,1.045,chr(97+i),transform=ax.transAxes,fontweight='bold',fontsize=10,va='bottom')

def save(fig,name,**kwargs):
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,json_out=str(QA/f'{name}.alignment.json'),strict=True,**kwargs)
    fig.savefig(FIG/f'q1_{name}.pdf')
    fig.savefig(FIG/f'q1_{name}.svg')
    fig.savefig(FIG/f'q1_{name}.png',dpi=300)
    plt.close(fig)
    print(name,flush=True)

# Three-dimensional view. Block maximum aggregation only for visualization.
# All underlying pixels participate; computational flight clearance uses original DEM.
fig=plt.figure(figsize=(W,5.0));ax=fig.add_subplot(111,projection='3d',computed_zorder=False)
lonlo=min(LON_O,areas.lon.min())-.012;lonhi=max(LON_O,areas.lon.max())+.012
latlo=min(LAT_O,areas.lat.min())-.012;lathi=max(LAT_O,areas.lat.max())+.012
cc=np.where((LON_C>=lonlo)&(LON_C<=lonhi))[0];rr=np.where((LAT_C>=latlo)&(LAT_C<=lathi))[0]
z=DEM[np.ix_(rr,cc)];block=4
nr=int(np.ceil(z.shape[0]/block));nc=int(np.ceil(z.shape[1]/block))
zpad=np.pad(z,((0,nr*block-z.shape[0]),(0,nc*block-z.shape[1])),constant_values=np.nan)
za=np.nanmax(zpad.reshape(nr,block,nc,block),axis=(1,3))
ll=np.array([LON_C[cc[min(i*block+block//2,len(cc)-1)]] for i in range(nc)])
la=np.array([LAT_C[rr[min(i*block+block//2,len(rr)-1)]] for i in range(nr)])
phi=np.radians(LAT_O);scaleX=A_WGS/np.sqrt(1-E2_WGS*np.sin(phi)**2)*np.cos(phi)*np.pi/180/1000
scaleY=A_WGS*(1-E2_WGS)/(1-E2_WGS*np.sin(phi)**2)**1.5*np.pi/180/1000
x=(ll-LON_O)*scaleX;y=(la-LAT_O)*scaleY;X,Y=np.meshgrid(x,y)
surf=ax.plot_surface(X,Y,za,cmap=LinearSegmentedColormap.from_list('elevation',['#D9E6DE','#AABEB0','#D5CEB6','#9B8D7D']),vmin=0,vmax=650,rcount=nr,ccount=nc,linewidth=0,antialiased=False,alpha=.65,rasterized=True,zorder=1)
for r in areas.itertuples():
    xx=(r.lon-LON_O)*scaleX;yy=(r.lat-LAT_O)*scaleY;h=SEG[r.id]['Hc']
    ax.plot([0,0,xx,xx],[0,0,yy,yy],[Z_O,h,h,r.elev+30],color=TC,alpha=.9,lw=1.0,zorder=3)
    ax.scatter(xx,yy,r.elev+30,s=9,c=TC,depthshade=False,zorder=4)
ax.scatter(0,0,Z_O,s=35,c='#9D3D44',marker='*',depthshade=False,zorder=5)
ax.set(xlabel='相对东向距离 (km)',ylabel='相对北向距离 (km)',zlabel='海拔 (m)')
ax.set_zlim(0,800);ax.view_init(elev=30,azim=-58);ax.set_box_aspect((np.ptp(x),np.ptp(y),4))
ax.tick_params(pad=1);ax.zaxis.labelpad=7
ax.set_xlabel('');ax.set_ylabel('')
fig.text(.22,.14,'相对东向距离 (km)',fontsize=9)
fig.text(.66,.19,'相对北向距离 (km)',fontsize=9)
ax.set_zticks([0,200,400,600,800]);ax.grid(False)
fig.text(.08,.94,'真实 DEM 地形与 15 条单点往返航线',fontsize=11,fontweight='bold')
fig.text(.08,.90,'星号：O01；蓝线：爬升—巡航—下降；高度方向视觉夸张',fontsize=8,color=GRAY)
fig.subplots_adjust(left=.02,right=.88,bottom=.06,top=.9)
cax=fig.add_axes([.89,.25,.018,.40]);fig.colorbar(surf,cax=cax,label='地面海拔 (m)')
save(fig,'terrain3d',exclude_axes=[cax])
(QA/'terrain_aggregation.json').write_text(json.dumps({'original_crop_shape':list(z.shape),'surface_shape':list(za.shape),'aggregation':'4x4 block maximum; edge blocks retain all pixels','calculation':'full-resolution DEM; no aggregation','vertical_display':'exaggerated; axes retain actual metres'},indent=2))

fig,axs=plt.subplots(1,3,figsize=(W,2.7),sharey=True)
for ax,aid in zip(axs,['S003','S008','S014']):
    g=SEG[aid];d=g['d']/1000;pr=g['profile'];xs=np.linspace(0,d,len(pr))
    ax.fill_between(xs,0,pr,color='#D6DED3');ax.plot(xs,pr,color='#7D8E7A',lw=.7)
    ax.plot([0,0,d,d],[Z_O,g['Hc'],g['Hc'],areas.set_index('id').loc[aid,'elev']+30],color=TC,lw=1.3)
    ax.set(xlabel='单程水平距离 (km)',ylim=(0,680));ax.set_xlim(-.15,d+.15)
axs[0].set_ylabel('海拔 (m)');panels(axs,['S003：较大爬升','S008：最远航段','S014：最高巡航海拔'])
fig.subplots_adjust(left=.09,right=.985,bottom=.21,top=.80,wspace=.22);save(fig,'profiles')

fig,axs=plt.subplots(1,3,figsize=(W,4.25),sharey=True,sharex=True)
for ax,g in zip(axs,TYPES):
    q=QMAX[g].to_numpy();yy=np.arange(15)
    ax.hlines(yy,0,q,color=COL[g],lw=1.8,alpha=.65)
    for j,a in enumerate(AREA_IDS):
        ax.plot(q[j],j,'o',color=COL[g],mec='#273a46' if QBIND.loc[a,g]=='能量' else 'white',mew=1,ms=5)
    ax.axvline(uav.loc[g,'Q'],color=GRAY,lw=.6,ls='--');ax.set(xlim=(0,86),xticks=[0,25,50,75],xlabel='最大安全载荷 (kg)')
    ax.set_yticks(yy,AREA_IDS);ax.grid(axis='x',color='#eeeeee',lw=.5)
axs[0].invert_yaxis();panels(axs,['A 型：结构约束','B 型：1 区能量约束','C 型：5 区能量约束'])
fig.subplots_adjust(left=.10,right=.98,bottom=.14,top=.88,wspace=.20);save(fig,'payload')

fig,ax=plt.subplots(figsize=(W,4.9));bidx=boxes.set_index('box')
for i,r in enumerate(plan):
    left=0
    for bid in r['boxes']:
        b=bidx.loc[bid];ax.barh(i,b.mass,left=left,height=.65,color=MATS[b.mat],edgecolor='white',linewidth=.6);left+=b.mass
    ax.text(left+1.2,i,f"{r['mass']:.0f}",va='center',fontsize=8)
ax.set_yticks(range(len(plan)),[f"{r['area']}-{r['sortie']}  {r['g']}型" for r in plan]);ax.invert_yaxis();ax.set(xlim=(0,86),xlabel='架次载荷 (kg)')
ax.legend(handles=[Patch(facecolor=c,label=k) for k,c in MATS.items()],ncol=4,loc='lower center',bbox_to_anchor=(.45,1.02),frameon=False,columnspacing=1)
ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
fig.subplots_adjust(left=.18,right=.97,top=.90,bottom=.13);save(fig,'batches')

front=pd.read_csv(R/'front.csv',index_col=0);pT=np.array(meta['pareto_points'][0]);pE=np.array(meta['pareto_points'][1]);ideal=np.array(meta['ideal']);cut=meta['weighted_boundary']['energy_weight_when_N_T_equal']
fig,axs=plt.subplots(1,2,figsize=(W,3.2))
ax=axs[0]
for p,c,label in [(pT,TC,'时间优先：18 架次'),(pE,EC,'能耗优先：19 架次')]:
    ax.scatter(p[1],p[2]/3600,s=65,c=c,zorder=3)
ax.text(pT[1]-.012,pT[2]/3600+.10,'18 架次 / R1、R3、R4',ha='right',fontsize=8,color=TC)
ax.text(pE[1]+.012,pE[2]/3600-.10,'19 架次 / R2',fontsize=8,color=EC)
ax.set(xlabel='总运输能耗 (kWh)',ylabel='累计作业时间 (h)',xlim=(59.01,59.16),ylim=(8.98,9.70))
ax.ticklabel_format(useOffset=False);ax.grid(False)
ax=axs[1];we=np.linspace(.9,1,501);wn=(1-we)/2
for p,col,lab in [(pT,TC,'时间优先方案'),(pE,EC,'能耗优先方案')]:
    score=wn*(p[0]/ideal[0]-1)+we*(p[1]/ideal[1]-1)+wn*(p[2]/ideal[2]-1)
    ax.plot(we,score*100,color=col,label=lab,lw=1.5)
ax.axvline(cut,color=GRAY,ls=':',lw=1);ax.set(xlabel='能耗权重 wE',ylabel='相对理想点的加权偏离 (%)',xlim=(.9,1),ylim=(0,.6))
ax.legend(loc='upper right',frameon=False);ax.text(.915,.52,'wN = wT = (1 − wE) / 2',fontsize=8)
ax.text(cut-.002,.27,f'{cut:.4f}',ha='right',fontsize=8,color=GRAY)
panels(axs,['完整 Pareto 前沿：仅两个点','偏好切换：聚焦高能耗权重区间'])
fig.subplots_adjust(left=.09,right=.98,bottom=.2,top=.82,wspace=.44);save(fig,'tradeoff')

fig,ax=plt.subplots(figsize=(W,2.4));rs=[r for k in ['R3','R2'] for r in plans[k] if r['area']=='S008']
for i,r in enumerate(rs):
    left=0
    for bid in r['boxes']:
        b=bidx.loc[bid];ax.barh(i,b.mass,left=left,color=MATS[b.mat],height=.5,edgecolor='white',linewidth=.6);left+=b.mass
    ax.text(48,i,f"{r['E']:.3f} kWh    {r['T']/60:.2f} min",va='center',fontsize=9)
ax.set_yticks(range(3),['时间优先：C 型','能耗优先：B 型（1）','能耗优先：B 型（2）']);ax.invert_yaxis();ax.set(xlim=(0,81),xlabel='架次载荷 (kg)',xticks=[0,15,30,45]);ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
fig.subplots_adjust(left=.25,right=.99,bottom=.27,top=.95);save(fig,'local_tradeoff')

pol=pd.read_csv(R/'policies.csv',index_col=0);fig,axs=plt.subplots(1,3,figsize=(W,2.9),sharey=True)
for ax,k,lab in zip(axs,['N','E','T_h'],['往返架次数','总运输能耗 (kWh)','累计作业时间 (h)']):
    vals=pol[k].to_numpy();yy=np.arange(5)
    ax.hlines(yy,0,vals,color='#CFD6DC',lw=2)
    ax.scatter(vals,yy,c=[GRAY]*4+[TC],s=35,zorder=3)
    for j,v in enumerate(vals):ax.text(v+max(vals)*.045,j,f'{v:.0f}' if k=='N' else f'{v:.2f}',va='center',fontsize=8)
    ax.set_yticks(yy,['仅 A','仅 B','仅 C','A+B','A+B+C']);ax.set(xlim=(0,max(vals)*1.35),xlabel=lab);ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
axs[0].invert_yaxis();panels(axs,['任务次数','能源投入','累计作业投入'])
fig.subplots_adjust(left=.10,right=.98,bottom=.22,top=.81,wspace=.20);save(fig,'policies')

sens=pd.read_csv(R/'sensitivity.csv',index_col=0);fig,axs=plt.subplots(1,3,figsize=(W,2.9))
for ax,k,lab in zip(axs,['N','E','T_h'],['往返架次数','总运输能耗 (kWh)','累计作业时间 (h)']):
    for rule,col,ls,label in [('TNE',TC,'-','时间优先'),('ENT',EC,'--','能耗优先')]:
        df=sens[(sens.rule==rule)&sens.complete];ax.plot(df.rho,df[k],color=col,ls=ls,lw=1.2,marker='.',ms=3,label=label)
    ax.axvspan(meta['rho_star'],.45,color='#ECEEEF',zorder=0);ax.axvline(.2,color=GRAY,lw=.7,ls=':');ax.set(xlim=(.05,.45),xlabel='返航安全余量 ρ',ylabel=lab,xticks=[.1,.2,.3,.4])
fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,1.01),ncol=2,frameon=False);panels(axs,['架次随约束收紧跳变','能耗并非随余量单调','累计作业时间的代价'])
fig.subplots_adjust(left=.08,right=.98,bottom=.22,top=.81,wspace=.43);save(fig,'sensitivity')

fig,axs=plt.subplots(1,2,figsize=(W,3.6));ax=axs[0]
rhos=np.linspace(.05,.48,431)
for g in TYPES:ax.plot(rhos,[max_safe_payload(uav.loc[g],SEG['S008'],v)[0] for v in rhos],color=COL[g],label=f'{g} 型',lw=1.5)
ax.axhline(14,color=GRAY,ls='--',lw=.8);ax.axvline(meta['rho_star'],color=GRAY,ls=':',lw=.8)
ax.text(.055,16,'单箱饮用水 14 kg',fontsize=8,color=GRAY);ax.set(xlabel='返航安全余量 ρ',ylabel='最大安全载荷 (kg)',xlim=(.05,.48),ylim=(0,85));ax.legend(loc='upper right',frameon=False)
ax=axs[1];limits=pd.read_csv(R/'singleton_boundaries.csv',index_col=0);lims=limits.groupby(['area','box']).rho_limit.max().groupby('area').min().reindex(AREA_IDS)
ax.barh(np.arange(15),lims,color=[EC if a=='S008' else '#AABCCB' for a in AREA_IDS],height=.63);ax.set_yticks(range(15),AREA_IDS);ax.invert_yaxis();ax.set(xlabel='该服务区完整配送余量上界',xlim=(0,.85));ax.axvline(.2,color=GRAY,ls=':',lw=.7)
panels(axs,['S008：载得动单箱才可完成配送','15 个服务区的解析可行边界'])
fig.subplots_adjust(left=.09,right=.97,bottom=.18,top=.84,wspace=.36);save(fig,'reserve')
