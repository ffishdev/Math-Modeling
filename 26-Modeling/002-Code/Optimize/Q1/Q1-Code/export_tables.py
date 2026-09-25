"""Generate paper tables directly from analyzed results; no manual result edits."""
from pathlib import Path
import json,pandas as pd
H=Path(__file__).resolve().parent;R=H/'results';L=H.parent/'Q1-latex';O=L/'tables';O.mkdir(exist_ok=True)
plans=json.loads((R/'plans.json').read_text());m=json.loads((R/'summary.json').read_text())
b=pd.read_csv(R/'boxes.csv',index_col=0).set_index('box');q=pd.read_csv(R/'qmax.csv',index_col=0);geo=pd.read_csv(R/'geometry.csv',index_col=0)
def table(name,caption,label,cols,head,rows,note=''):
 s='\\begin{table}[!htbp]\n\\centering\n\\caption{'+caption+'}\n\\label{tab:q1-'+label+'}\n\\small\n\\setlength{\\tabcolsep}{4pt}\n\\renewcommand{\\arraystretch}{1.10}\n\\begin{tabular}{@{}'+cols+'@{}}\n\\toprule\n'+head+' \\\\\n\\midrule\n'
 s+='\n'.join(' & '.join(map(str,row))+' \\\\' for row in rows)
 s+='\n\\bottomrule\n\\end{tabular}\n'
 if note:s+='\\par\\smallskip{\\footnotesize '+note+'}\n'
 s+='\\end{table}\n';(O/(name+'.tex')).write_text(s)
rows=[[a,f'{geo.loc[a,"d"]/1000:.2f}',f'{geo.loc[a,"Hc"]:.2f}',*[f'{q.loc[a,g]:.2f}' for g in 'ABC']] for a in q.index]
table('payload','基准返航安全余量下的最大安全载荷','payload','lrrrrr','服务区 & 距离（km） & 巡航海拔（m） & A（kg） & B（kg） & C（kg）',rows,'最大载荷仅表示质量与能量允许的连续上界；实际组批还须满足体积约束。')
rows=[]
for r in plans['R3']:
 counts=[sum(b.loc[x,'mat']==k for x in r['boxes']) for k in ['医疗物资','饮用水','应急食品','生活卫生用品']]
 rows.append([r['area']+'-'+str(r['sortie']),r['g'],'/'.join(map(str,counts)),f"{r['mass']:.0f}",f"{r['vol']:.3f}",f"{r['E']:.3f}",f"{r['T']/60:.2f}"])
table('plan','时间优先推荐方案的逐架次装载与代价','plan','llcrrrr','架次 & 机型 & 箱数向量 & 质量（kg） & 体积（m$^3$） & 能耗（kWh） & 时间（min）',rows,'箱数向量按医疗物资、饮用水、应急食品、生活卫生用品排列；同一区的架次序号仅用于标识，不表示已完成时序调度。')
r=pd.read_csv(R/'rules.csv',index_col=0)
table('rules','四种偏好规则与全局前沿点的对应关系','rules','llrrrl','规则 & 优先关系 & 架次数 & 能耗（kWh） & 时间（h） & 选定点',[[k,{'R1':'$N\\to E\\to T$','R2':'$E\\to N\\to T$','R3':'$T\\to N\\to E$','R4':'理想值归一化等权'}[k],int(v.N),f'{v.E:.3f}',f'{v.T_h:.3f}','$P_E$' if k=='R2' else '$P_T$'] for k,v in r.iterrows()],'R3 为本章推荐规则；R1、R3、R4 在本测试场景中恰好选中同一目标向量。')
p=pd.read_csv(R/'policies.csv',index_col=0)
table('policies','统一采用时间优先规则的机型可用集合比较','policies','lrrr','机型集合 & 架次数 & 能耗（kWh） & 时间（h）',[[k,int(v.N),f'{v.E:.3f}',f'{v.T_h:.3f}'] for k,v in p.iterrows()])
s=pd.read_csv(R/'sensitivity.csv',index_col=0);s=s[(s.rule=='TNE')&s.rho.isin([.05,.1,.15,.2,.25,.3,.35,.36,.4,.45])]
table('sensitivity','返航安全余量扫描的时间优先组批结果','sensitivity','rrrrl','$\\rho$ & 架次数 & 能耗（kWh） & 时间（h） & 完整配送',[[f'{v.rho:.2f}',int(v.N) if v.complete else '--',f'{v.E:.3f}' if v.complete else '--',f'{v.T_h:.3f}' if v.complete else '--','可行' if v.complete else '不可行'] for _,v in s.iterrows()],'不可行时不以已覆盖服务区的部分合计冒充全局结果。扫描步长为 0.01，精确边界另由单箱可行性推导。')
print('generated',len(list(O.glob('*.tex'))),'tables')
