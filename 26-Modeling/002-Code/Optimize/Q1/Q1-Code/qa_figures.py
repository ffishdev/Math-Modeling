"""Run final-source and rendered-PDF checks using the installed figure skill."""
import os,sys,subprocess,json
from pathlib import Path
H=Path(__file__).resolve().parent;F=H.parent/'Q1-latex/figures';Q=H/'qa'
S=Path(os.environ.get('NATURE_FIGURE_SKILL',str(Path.home()/'.agents/skills/nature-figure')))/'scripts'
reports=[]
for p in sorted(F.glob('*.pdf')):
 for script,args,kind in [('audit_pdf_text.py',['--min-pt','5','--json'],'text'),('audit_figure_collisions.py',['--json-out',str(Q/(p.stem+'.collision.json'))],'collision')]:
    proc=subprocess.run([sys.executable,str(S/script),str(p),*args],capture_output=True,text=True)
    (Q/(p.stem+'.'+kind+'.log')).write_text(proc.stdout+proc.stderr)
    reports.append({'figure':p.name,'check':kind,'exit':proc.returncode})
proc=subprocess.run([sys.executable,str(S/'validate_figure.py'),str(H/'plot_figures.py'),'--json'],capture_output=True,text=True)
(Q/'source_validation.json').write_text(proc.stdout+proc.stderr)
(Q/'check_summary.json').write_text(json.dumps(reports,indent=2));print(json.dumps(reports,indent=2))
