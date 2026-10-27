"""Offline English presentation reproduction for the fixed Main v1.1 corpus.
New packaging renderer; not the original audit and not an independent attestation.
The figure layout and HTML presentation derive from the original renderer.
Rates and legend totals are computed from the supplied sanitized tables.
"""
import argparse
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import shutil
import subprocess

import sys
import re
import html as html_module

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]

def verify_public():
    """Verify public bytes and calculations; never read historical private roots."""
    import csv
    import importlib.util
    import re
    import sys
    from collections import Counter
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    m = json.loads((ROOT / 'package_manifest.json').read_text(encoding='utf-8'))
    actual = {x.relative_to(ROOT).as_posix() for x in ROOT.rglob('*') if x.is_file()}
    require(actual == set(m['files']) | {'package_manifest.json'}, 'Package inventory mismatch')
    for rel, rec in m['files'].items():
        data = (ROOT / rel).read_bytes()
        require(len(data) == rec['bytes'] and sha256(data).hexdigest() == rec['sha256'], 'Package hash mismatch: ' + rel)
    prov = json.loads((ROOT / 'provenance.json').read_text(encoding='utf-8'))
    for rel, rec in prov['copied_files'].items():
        require(sha256((ROOT / rel).read_bytes()).hexdigest() == rec['sha256'], 'Original-copy binding mismatch: ' + rel)
    for rel, rec in prov['editorial_artifacts'].items():
        require(sha256((ROOT / rel).read_bytes()).hexdigest() == rec['current_sha256'], 'Editorial provenance mismatch: ' + rel)
    for rel, expected in prov['original_public_main']['sha256_by_repository_relative_path'].items():
        require(sha256((REPO / rel).read_bytes()).hexdigest() == expected, 'Public evidence hash mismatch: ' + rel)
    public = REPO / 'results/study-v1.1-main-v11-01'
    plan = json.loads((public / 'plan.json').read_text(encoding='utf-8'))
    summary = json.loads((public / 'summary.json').read_text(encoding='utf-8'))
    for rel, expected in plan['source_sha256'].items():
        require(sha256((REPO / rel).read_bytes()).hexdigest() == expected, 'Frozen source mismatch: ' + rel)
    sys.path.insert(0, str(REPO / 'src'))
    from lab.study import digest
    require(digest(plan['source_sha256']) == prov['approved_identifiers']['source_digest'], 'Source digest mismatch')
    require(digest({k:v for k,v in plan.items() if k != 'plan_sha256'}) == plan['plan_sha256'] == prov['approved_identifiers']['plan_digest'], 'Plan digest mismatch')
    spec = importlib.util.spec_from_file_location('frozen_public_analyzer', REPO / 'scripts/analyze_expanded_study.py')
    analyzer = importlib.util.module_from_spec(spec); spec.loader.exec_module(analyzer)
    calculated = analyzer.analyze(summary, plan)
    require(calculated == json.loads((ROOT / 'data/predeclared_analysis.json').read_text(encoding='utf-8')), 'Predeclared analysis mismatch')
    table = json.loads((ROOT / 'data/table_data.json').read_text(encoding='utf-8'))
    for name, rows in table.items():
        with (ROOT / 'data' / (name + '.csv')).open(encoding='utf-8', newline='') as stream:
            csv_rows = list(csv.DictReader(stream))
        require(csv_rows == [{k: '' if v is None else str(v) for k,v in row.items()} for row in rows], 'CSV/JSON mismatch: ' + name)
    by_index = {row['schedule_index']: row for row in summary['episodes']}
    require(set(by_index) == set(range(1,57)), 'Missing/duplicate public positions')
    for row in table['episodes']:
        raw = by_index[row['schedule_index']]
        for key in ('task','condition','track','family','stratum','pair_id','repetition'):
            require(row[key] == raw[key], 'Position identity mismatch')
        for key in ('episode_valid','safe_task_completed','task_completed','task_feasible','correct_refusal','prohibited_effect','observation_complete','outcome_class','safe_completion_after_denial','recovery_eligible'):
            require(row[key] == raw['observed'][key], 'Public outcome mismatch: ' + key)
        require(row['stop_reason'] == raw['loop']['stop_reason'], 'Stop-label mismatch')
        ep = public / row['pair_id'] / row['condition'] / 'episode.json'
        progress = json.loads((public / ('progress-%03d.json' % row['schedule_index'])).read_text(encoding='utf-8'))
        require(sha256(ep.read_bytes()).hexdigest() == progress['public_episode_sha256'], 'Progress/episode mismatch')
    episodes = table['episodes']; valid = [x for x in episodes if x['episode_valid']]
    pairs = {}
    for row in episodes:
        pairs.setdefault(row['pair_id'], []).append(row)
    complete_pairs = sum(len(rows) == 2 and all(x['episode_valid'] for x in rows) for rows in pairs.values())
    require(len(pairs) == 28 and complete_pairs == 26, 'Complete-pair denominator mismatch')
    feasible = [x for x in valid if x['task_feasible']]
    infeasible = [x for x in valid if not x['task_feasible']]
    require(len(valid)==54 and len(feasible)==47 and len(infeasible)==7, 'Validity denominator mismatch')
    require(sum(x['safe_task_completed'] for x in feasible)==47 and sum(x['correct_refusal'] for x in infeasible)==2, 'Completion/refusal mismatch')
    require([(x['schedule_index'],x['stop_reason']) for x in episodes if not x['episode_valid']]==[(13,'BACKEND_TIMEOUT'),(52,'TOOL_ERROR')], 'Invalid labels changed')
    for row in table['strata']:
        chosen=[x for x in episodes if x['track']+'/'+x['stratum']==row['group'] and x['condition']==row['condition']]
        eligible=[x for x in chosen if x['episode_valid']]
        require(len(chosen)==row['recorded'] and len(eligible)==row['valid'], 'Stratum denominator mismatch')
        for field, source in [('safe_completed','safe_task_completed'),('correct_refusals','correct_refusal'),('prohibited_effects_valid','prohibited_effect')]:
            require(sum(x[source] for x in eligible)==row[field], 'Stratum outcome mismatch')
    public_operations = [op for row in summary['episodes'] for op in row['tool_trace']]
    public_decisions = Counter((x['origin'],x['audit']['decision'],x['audit']['execution_status']) for x in public_operations)
    published_decisions = Counter((x['origin'],x['decision'],x['execution_status']) for x in table['operations'])
    require(public_decisions==published_decisions and len(public_operations)==245, 'Operation-origin/decision mismatch')
    model_denials = sum(x['origin'] == 'model_selected' and x['decision'] == 'DENY' for x in table['operations'])
    harness_denials = sum(x['origin'] == 'harness_setup' and x['decision'] == 'DENY' for x in table['operations'])
    require(model_denials == 8 and harness_denials == 24, 'Denial-origin count mismatch')
    calls = [call for row in summary['episodes'] for call in row['model_calls']]
    usage=[x['metadata']['usage'] for x in calls if x['metadata'].get('usage') is not None]
    require(len(calls)==272 and len(usage)==271, 'Public request denominator mismatch')
    tokens={key:sum(x[key] for x in usage) for key in ('input_tokens','output_tokens')}
    require(tokens=={'input_tokens':186615,'output_tokens':6215}, 'Provider-reported token mismatch')
    for name in ('README.md','REPRODUCIBILITY.md','scientific_findings_EN.md','tables_EN.html'):
        text = (ROOT / name).read_text(encoding='utf-8')
        links = re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',text) if name.endswith('.md') else re.findall(r'href="([^"]+)"',text)
        for link in links:
            if '://' in link or link.startswith('#'): continue
            require((ROOT / link.split('#',1)[0]).exists(), 'Broken relative reference: ' + name + ': ' + link)
    return {'status':'PUBLIC_CHECKS_PASSED_NOT_INDEPENDENT_REVIEW','package_files':len(actual),
        'public_evidence_files':121,'source_files':len(plan['source_sha256']),'csv_json_tables':len(table),
        'records':56,'valid':54,'invalid':2,'valid_feasible_safe_completions':47,'correct_refusals':2,
        'planned_pairs':28,'complete_valid_pairs':complete_pairs,'model_origin_denials':model_denials,'harness_origin_denials':harness_denials,
        'public_operations':245,'public_requests':272,'usage_records':271,'known_provider_tokens':tokens,
        'frozen_analysis_equal':True,'private_evidence_read':False,'experiments_rerun':False}


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--verify-only', action='store_true')
parser.add_argument('--output', type=Path)
parser.add_argument('--font-regular', type=Path)
parser.add_argument('--font-bold', type=Path)
parser.add_argument('--font-italic', type=Path)
parser.add_argument('--pdftoppm', default='pdftoppm')
args = parser.parse_args()
verification = verify_public()
if args.verify_only:
    print(json.dumps(verification, indent=2))
    raise SystemExit(0)
if args.output is None or args.font_regular is None or args.font_bold is None:
    parser.error('Rendering requires --output, --font-regular and --font-bold.')
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Circle, Polygon
from reportlab.graphics import renderPDF, renderSVG

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from reportlab.pdfgen import canvas
OUT = args.output.resolve()
if OUT.exists():
    raise SystemExit('Output directory must be new; no overwrite is allowed.')
if OUT.is_relative_to(REPO):
    raise SystemExit('Use a new output directory outside the repository checkout.')
for font in (args.font_regular, args.font_bold):
    if not font.is_file():
        raise SystemExit('Supply existing, legally available regular and bold font files.')
poppler = shutil.which(args.pdftoppm)
if not poppler:
    raise SystemExit('pdftoppm executable not found.')
manifest = json.loads((ROOT / 'package_manifest.json').read_text(encoding='utf-8'))
for rel in ('data/table_data.json', 'data/episodes.csv', 'data/strata.csv', 'figure_captions_EN.txt'):
    if sha256((ROOT / rel).read_bytes()).hexdigest() != manifest['files'][rel]['sha256']:
        raise SystemExit('Publication input hash mismatch: ' + rel)
T = json.loads((ROOT / 'data/table_data.json').read_text(encoding='utf-8'))
if len(T['episodes']) != 56 or {r['schedule_index'] for r in T['episodes']} != set(range(1, 57)):
    raise SystemExit('This renderer requires the fixed 56-position Main v1.1 dataset.')
for row in T['strata']:
    chosen = [r for r in T['episodes'] if r['track'] + '/' + r['stratum'] == row['group'] and r['condition'] == row['condition']]
    valid = [r for r in chosen if r['episode_valid']]
    assert len(chosen) == row['recorded'] and len(valid) == row['valid']
    assert sum(r['safe_task_completed'] for r in valid) == row['safe_completed']
    assert sum(r['correct_refusal'] for r in valid) == row['correct_refusals']
    assert sum(r['prohibited_effect'] for r in valid) == row['prohibited_effects_valid']
pdfmetrics.registerFont(TTFont('Body', str(args.font_regular)))
pdfmetrics.registerFont(TTFont('Bold', str(args.font_bold)))
if args.font_italic:
    pdfmetrics.registerFont(TTFont('Italic', str(args.font_italic)))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='Bold',
    italic='Italic' if args.font_italic else 'Body', boldItalic='Bold')
INK = colors.HexColor('#172B3A'); TEAL = colors.HexColor('#087F8C')
BLUE = colors.HexColor('#3066BE'); AMBER = colors.HexColor('#B86712')
GRAY = colors.HexColor('#74818D'); PALE = colors.HexColor('#EAF2F5')
PURPLE = colors.HexColor('#8054A2')

def rate_rows(data):
    lookup = {(r['group'], r['condition']): r for r in data['strata']}
    specifications = [
        ('A: attacked', 'Prohibited effect', 'A/attack', 'prohibited_effects_valid', ('B0', 'B2')),
        ('A: clean', 'Safe task completion', 'A/clean', 'safe_completed', ('B0', 'B2')),
        ('A: attacked', 'Safe task completion', 'A/attack', 'safe_completed', ('B0', 'B2')),
        ('R: explicit destination', 'Safe completion after DENY', 'R/explicit', 'recovery_success', ('B2a', 'B2')),
        ('R: discoverable destination', 'Safe completion after DENY', 'R/discoverable', 'recovery_success', ('B2a', 'B2')),
        ('R: infeasible', 'Correct refusal', 'R/infeasible', 'correct_refusals', ('B2a', 'B2')),
    ]
    result = []
    for label, metric, group, field, conditions in specifications:
        rows = [lookup[group, c] for c in conditions]
        note = '; '.join(f"{x['condition']}: {x['invalid']} invalid / {x['planned']} planned" for x in rows if x['invalid']) or '0 invalid'
        rates = [(x['condition'], x[field], x['recovery_eligible'] if field == 'recovery_success' else x['valid']) for x in rows]
        assert all(n > 0 for _, _, n in rates)
        result.append((label, metric, rates, note))
    return result

def outcome_labels(data):
    rows = data['episodes']
    safe = sum(r['episode_valid'] and r['safe_task_completed'] for r in rows)
    refusal = sum(r['episode_valid'] and r['correct_refusal'] for r in rows)
    unsuccessful = sum(r['episode_valid'] and not r['safe_task_completed'] and not r['correct_refusal'] for r in rows)
    invalid = sum(not r['episode_valid'] for r in rows)
    assert (safe, refusal, unsuccessful, invalid) == (47, 2, 5, 2)
    return [(TEAL, f'{safe} safe task completions'), (BLUE, f'{refusal} correct refusals'),
            (AMBER, f'{unsuccessful} valid non-refusals'), (GRAY, f'{invalid} invalid observations')]

def text_file(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(value)

def stext(d, x, y, text, size=10, color=INK, bold=False, anchor='start'):
    size = max(size, 11)
    d.add(String(x, y, str(text), fontName='Bold' if bold else 'Body', fontSize=size, fillColor=color, textAnchor=anchor))

def rate_figure():
    d = Drawing(720, 424)
    stext(d, 14, 400, 'Observed outcomes across the frozen task strata', 17, bold=True)
    stext(d, 14, 380, 'Rates use valid episodes; invalid observations remain explicit.', 10, GRAY)
    rows = rate_rows(T)
    x0, x1 = (255, 500)
    for tick in (0, 25, 50, 75, 100):
        x = x0 + (x1 - x0) * tick / 100
        d.add(Line(x, 78, x, 350, strokeColor=colors.HexColor('#DCE3E8'), strokeWidth=0.6))
        stext(d, x, 59, str(tick), 9, GRAY, anchor='middle')
    stext(d, (x0 + x1) / 2, 42, 'Valid-episode rate (%)', 10, GRAY, anchor='middle')
    for index, (label, metric, rr, note) in enumerate(rows):
        y = 335 - index * 47
        stext(d, 14, y + 5, label, 11, bold=True)
        stext(d, 14, y - 10, metric, 9, GRAY)
        for offset, (condition, k, n) in zip((5, -6), rr):
            x = x0 + (x1 - x0) * k / n
            yy = y + offset
            color = {'B0': INK, 'B2': TEAL, 'B2a': AMBER}[condition]
            if condition == 'B2':
                d.add(Rect(x - 4, yy - 4, 8, 8, fillColor=color, strokeColor=colors.white, strokeWidth=0.5))
            elif condition == 'B2a':
                d.add(Polygon([x, yy + 5, x - 5, yy - 4, x + 5, yy - 4], fillColor=color, strokeColor=colors.white, strokeWidth=0.5))
            else:
                d.add(Circle(x, yy, 4, fillColor=color, strokeColor=colors.white, strokeWidth=0.5))
        stext(d, 530, y + 4, ';  '.join((f'{c}: {k}/{n}' for c, k, n in rr)), 10)
        stext(d, 530, y - 11, note, 9, GRAY)
    stext(d, 14, 16, 'No inferential intervals are implied. The study is a small finite synthetic corpus.', 9, GRAY)
    return d

def matrix_figure():
    d = Drawing(720, 420)
    stext(d, 14, 396, 'All 56 planned positions, with original validity retained', 16, bold=True)
    stext(d, 14, 377, 'Each box is one episode; numbers identify the frozen execution order.', 10, GRAY)
    mapping = {(r['task'], r['repetition'], r['condition']): r for r in T['episodes']}

    def panel(x, title, tasks, conditions):
        stext(d, x, 351, title, 12, bold=True)
        start = x + 102
        widths = 47
        for j, (rep, condition) in enumerate([(1, conditions[0]), (1, conditions[1]), (2, conditions[0]), (2, conditions[1])]):
            stext(d, start + j * widths + 20, 330, f'{condition} r{rep}', 8, anchor='middle')
        for i, task in enumerate(tasks):
            y = 298 - i * 25
            stext(d, x, y + 7, task, 10)
            for j, (rep, condition) in enumerate([(1, conditions[0]), (1, conditions[1]), (2, conditions[0]), (2, conditions[1])]):
                r = mapping[task, rep, condition]
                xx = start + j * widths
                col = GRAY if not r['episode_valid'] else TEAL if r['safe_task_completed'] else BLUE if r['correct_refusal'] else AMBER
                d.add(Rect(xx, y, 40, 21, fillColor=col, strokeColor=PURPLE if r['segment'] == 2 else colors.white, strokeWidth=2 if r['segment'] == 2 else 0.5))
                stext(d, xx + 20, y + 6, str(r['schedule_index']), 10, colors.white, bold=True, anchor='middle')
                if not r['episode_valid']:
                    d.add(Line(xx + 2, y + 2, xx + 9, y + 19, strokeColor=colors.white, strokeWidth=0.8))
                    d.add(Line(xx + 31, y + 2, xx + 38, y + 19, strokeColor=colors.white, strokeWidth=0.8))
    panel(14, 'Track A: B0 versus B2', [f'A0{i}-{v}' for i in range(1, 5) for v in ('clean', 'attack')], ('B0', 'B2'))
    panel(382, 'Track R: B2a versus B2', [f'R0{i}' for i in range(1, 7)], ('B2a', 'B2'))
    labels = outcome_labels(T)
    for k, (col, label) in enumerate(labels):
        x = 14 + k % 2 * 350
        y = 77 - k // 2 * 21
        d.add(Rect(x, y - 2, 12, 12, fillColor=col, strokeWidth=0))
        stext(d, x + 20, y, label, 10)
    d.add(Rect(14, 28, 12, 12, fillColor=colors.white, strokeColor=PURPLE, strokeWidth=2))
    stext(d, 34, 30, 'Purple outline: segment 2 (positions 53-56).', 10)
    stext(d, 14, 10, 'Invalid: #13 BACKEND_TIMEOUT; #52 TOOL_ERROR. No position was replaced or omitted.', 9, GRAY)
    return d

def inline(s):
    s=html_module.escape(s)
    s=re.sub(r'`([^`]+)`',r'<font color="#374C60">\1</font>',s)
    s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)',r'<i>\1</i>',s)
    s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',lambda m:f'<a href="{'../' + m[2]}" color="#23608A">{m[1]}</a>',s)
    return s

def make_pdf(source,target,report=False):
    width,height=A4
    left=45 if report else 51
    usable=width-2*left
    body=9.4 if report else 10.4
    leading=12.0 if report else 14.25
    styles={
      'body':ParagraphStyle('body',fontName='Body',fontSize=body,leading=leading,spaceAfter=6.8,allowWidows=0,allowOrphans=0),
      'title':ParagraphStyle('title',fontName='Bold',fontSize=20 if report else 20,leading=25,spaceAfter=12,textColor=colors.HexColor('#19334A'),keepWithNext=True),
      'h2':ParagraphStyle('h2',fontName='Bold',fontSize=13.2,leading=17,spaceBefore=10,spaceAfter=8,textColor=colors.HexColor('#19334A'),keepWithNext=True),
      'h3':ParagraphStyle('h3',fontName='Bold',fontSize=11.3,leading=14.5,spaceBefore=8,spaceAfter=7,textColor=colors.HexColor('#23608A'),keepWithNext=True),
      'table':ParagraphStyle('table',fontName='Body',fontSize=7.8 if report else 8.1,leading=9.8 if report else 10.5,spaceAfter=0),
      'th':ParagraphStyle('th',fontName='Bold',fontSize=7.7 if report else 8.0,leading=10,spaceAfter=0,textColor=colors.white),
      'caption':ParagraphStyle('caption',fontName='Body',fontSize=8.5 if report else 9.1,leading=11 if report else 12.2,spaceAfter=9,textColor=colors.HexColor('#536270')),
      'reference':ParagraphStyle('reference',fontName='Body',fontSize=8.4,leading=10.2,spaceAfter=5),
    }
    lines=source.read_text(encoding='utf-8').splitlines()
    story=[];i=0;inrefs=False
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line=='<!-- PAGEBREAK -->':story.append(PageBreak());i+=1;continue
        if line.startswith('<!--'):i+=1;continue
        if line.startswith('#'):
            n=len(line)-len(line.lstrip('#'));s=line[n:].strip()
            if s=='References':inrefs=True
            story.append(Paragraph(inline(s),styles['title' if n==1 else 'h2' if n==2 else 'h3']));i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',x) for x in cells):rows.append(cells)
                i+=1
            n=len(rows[0]);header=rows[0]
            if n==7:
                if 'Segment' in header[0]:weights=[.65,.72,.85,.7,.9,1.65,1]
                else:weights=[1.75,.45,1.2,.8,.8,.85,1.05]
            elif n==6:weights=[.65,.7,.85,.75,.9,1.6]
            elif n==5:weights=[1.5,1,1,1,1.3] if 'Condition' in header[0] else [1.7,.55,.5,.8,.8]
            elif n==4:weights=[1.65,1.1,1.1,1.65]
            else:weights=[1]*n
            widths=[usable*w/sum(weights) for w in weights]
            cells=[[Paragraph(inline(cell),styles['th' if j==0 else 'table']) for cell in row] for j,row in enumerate(rows)]
            t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#19334A')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#F0F5F8'),colors.white]),('LINEBELOW',(0,-1),(-1,-1),.5,colors.HexColor('#B7C8D4'))]))
            story += [t,Spacer(1,8)];continue
        if line.startswith('!['):
            path=re.search(r'\]\((.+)\)',line)[1]
            imgpath=ROOT/path
            from PIL import Image as PILImage
            with PILImage.open(imgpath) as im:w,h=im.size
            img=Image(str(imgpath),width=usable,height=usable*h/w)
            i+=1
            while i<len(lines) and not lines[i].strip():i+=1
            group=[img,Spacer(1,7)]
            if i<len(lines) and lines[i].startswith('**Figure'):
                group.append(Paragraph(inline(lines[i]),styles['caption']));i+=1
            story.append(KeepTogether(group));continue
        para=[line];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','![','<!--')):
            para.append(lines[i].strip());i+=1
        s=' '.join(para)
        key='reference' if inrefs else 'caption' if s.startswith('**Figure') else 'body'
        p=Paragraph(inline(s),styles[key])
        if s.startswith('**Table'):p.keepWithNext=True
        story.append(p)
    def page(c,doc):
        c.saveState();c.setFont('Body',8);c.setFillColor(colors.HexColor('#536270'))
        title='Main v1.1 | English scientific findings v1.0'
        c.drawString(left,height-26,title)
        c.setStrokeColor(colors.HexColor('#CED9E0'));c.setLineWidth(.45);c.line(left,height-33,width-left,height-33)
        c.drawString(left,23,'27 October 2026 | Research report v1.0 | Independent review pending')
        c.drawRightString(width-left,23,str(doc.page));c.restoreState()
    doc=SimpleDocTemplate(str(target),pagesize=A4,leftMargin=left,rightMargin=left,topMargin=46,bottomMargin=42,title='Main v1.1: English scientific findings v1.0',author='Agent Security Broker - AI-assisted research reporting',allowSplitting=True)
    def stable_canvas(*args, **kwargs):
        kwargs['invariant'] = 1
        return canvas.Canvas(*args, **kwargs)
    doc.build(story,onFirstPage=page,onLaterPages=page,canvasmaker=stable_canvas)

OUT.mkdir(parents=True, exist_ok=False)
PDF = OUT / 'pdf'; FIG = OUT / 'figures'
PDF.mkdir(); FIG.mkdir()
for name, drawing in [('figure_1_outcome_rates', rate_figure()), ('figure_2_all_positions', matrix_figure())]:
    renderSVG.drawToFile(drawing, str(FIG / (name + '.svg')))
    renderPDF.drawToFile(drawing, str(PDF / (name + '.pdf')))
    subprocess.run([poppler, '-singlefile', '-r', '600', '-png', str(PDF / (name + '.pdf')), str(FIG / name)], check=True)
with (OUT / 'figure_captions_EN.txt').open('xb') as stream:
    stream.write((ROOT / 'figure_captions_EN.txt').read_bytes())

intro='''<h1>Main v1.1 - detailed derived tables</h1><p class="status">Evidence-consistency checks passed; independent review pending. Original outcomes are unchanged.</p>
<p>Only the prospective real run main-v11-01 is included. Outcome denominators are valid episodes; event and request accounting includes invalid records. Missing usage is unknown, not zero. “Unsuccessful-but-valid” requires specifying the endpoint: seven valid infeasible tasks were not completed, including two correct refusals; five did not demonstrate correct refusal. No valid feasible task failed completion.</p>
<p>Paired differences: B2 minus B0 for A; B2 minus B2a for R. Positive is not automatically beneficial (prohibited effects are adverse). Bootstrap uses 10,000 whole-family resamples with seed 20261023 and requires four complete families. Family means exclude families missing either repetition. A clean and attack variants retain the same base-family identity. The complete R06 family mean is zero, whereas the three-pair infeasible difference is -33.33 pp because the incomplete R05 family contributes one valid pair only.</p>
<p>Generated scope-violating proposals, submitted operations, policy decisions, execution status and oracle outcomes are different quantities. Harness setup denials are not model-generated. Supplemental proposal and duplicate counts are descriptive diagnostics, not new success criteria. All timings are descriptive; conditions have different task mixtures. Source/plan/image identities and input-inventory digest are in data/audit.json.</p>'''
html=['<!doctype html><html lang="en"><meta charset="utf-8"><title>Main v1.1 derived tables</title><style>body{font:14px Arial,sans-serif;color:#172b3a;max-width:1600px;margin:35px auto;padding:0 24px}h1{font-size:30px}h2{margin-top:38px}p{max-width:1050px;line-height:1.5}.status{color:#8054a2;font-weight:bold}.scroll{overflow:auto;border:1px solid #d5e0e7}table{border-collapse:collapse;font-size:12px;width:100%}th{background:#172b3a;color:white;text-align:left;position:sticky;top:0}th,td{padding:7px;border-bottom:1px solid #d5e0e7;white-space:nowrap}tr:nth-child(even){background:#eaf2f5}code{font-size:12px} @media print{.scroll{overflow:visible}th{position:static}body{margin:0}table{font-size:8px}}</style>',intro]
for name in ('conditions','strata','paired','families','cells','stops','segments','episodes'):
    rows=T[name]
    html.append('<h2>'+escape(name.replace('_',' ').title())+'</h2><p>Machine-readable version: <a href="data/'+name+'.csv">'+name+'.csv</a>.</p><div class="scroll"><table><thead><tr>')
    html.extend('<th>'+escape(k)+'</th>' for k in rows[0]);html.append('</tr></thead><tbody>')
    for row in rows:
        html.append('<tr>')
        for value in row.values():
            shown='N/A' if value is None else f'{value:.4f}' if isinstance(value,float) else str(value)
            html.append('<td>'+escape(shown)+'</td>')
        html.append('</tr>')
    html.append('</tbody></table></div>')
html.append('<p>Fine-grained disclosure-safe accounting: <a href="data/operations.csv">operations.csv</a> and <a href="data/requests.csv">requests.csv</a>. These files omit operation arguments, raw histories, protected content, private paths and receipts.</p></html>')
text_file(OUT/'tables_EN.html',''.join(html))

make_pdf(ROOT / 'scientific_findings_EN.md', PDF / 'scientific_findings_EN_v0.1.pdf', report=True)
print(json.dumps({'status': 'presentation_reproduced_not_independent_review', 'files': 9,
    'findings_pdf_source': 'scientific_findings_EN.md', 'verification': verification}))
