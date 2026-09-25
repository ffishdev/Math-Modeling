"""Render every chapter page for visual inspection and record static checks."""
from pathlib import Path
import json,re
import pymupdf
from PIL import Image,ImageDraw
H=Path(__file__).resolve().parent;L=H.parent/'Q1-latex';O=H/'qa/pages';O.mkdir(exist_ok=True)
doc=pymupdf.open(L/'build/Q1.pdf')
for old in O.glob('*.png'):old.unlink()
for i,page in enumerate(doc):page.get_pixmap(matrix=pymupdf.Matrix(1.4,1.4)).save(O/f'page_{i+1:02}.png')
for i in range(0,len(doc),2):
 canvas=Image.new('RGB',(1700,1240),'#cccccc')
 for j in range(2):
  if i+j>=len(doc):break
  im=Image.open(O/f'page_{i+j+1:02}.png');im.thumbnail((835,1190));canvas.paste(im,(j*850,30));ImageDraw.Draw(canvas).text((j*850+10,5),f'PAGE {i+j+1}',fill='black')
 canvas.save(O/f'pair_{i//2+1}.png')
log=(L/'build/Q1.log').read_text();tex=(L/'chapter.tex').read_text();text='\n'.join(p.get_text() for p in doc)
report={'pages':len(doc),'figures':len(re.findall(r'\\begin\{figure\}',tex)),'tables':len(list((L/'tables').glob('*.tex'))),'overfull':len(re.findall('Overfull',log)),'undefined_references':bool(re.search('undefined|multiply defined',log,re.I)),'missing_glyphs':bool(re.search('Missing character',log)),'pdf_text_contains_unresolved_refs':'??' in text,'warnings':[x for x in log.splitlines() if 'Warning:' in x]}
assert not report['overfull'] and not report['undefined_references'] and not report['missing_glyphs'] and not report['pdf_text_contains_unresolved_refs']
(H/'qa/paper_checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(report)
