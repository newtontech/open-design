#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, re, shutil, zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
NS = {"w": W_NS, "m": M_NS, "r": R_NS}
ET.register_namespace("w", W_NS); ET.register_namespace("m", M_NS); ET.register_namespace("r", R_NS)
COMMENTS_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
COMMENTS_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"

true=True; false=False; null=None
CONFIG = {
  "name": "docx-abbreviation-after-definition",
  "display": "DOCX Abbreviation After Definition",
  "short": "Use abbreviations after definition.",
  "prompt": "Check this DOCX for repeated full terms after abbreviation definition.",
  "desc": "Use when checking or fixing DOCX abbreviation consistency after first definition, such as using ML after machine learning has been defined.",
  "mode_desc": "repeated full terms after their abbreviation has already been defined.",
  "mode": "abbrev",
  "definitions": [
    {
      "phrase": "machine learning",
      "abbr": "ML"
    },
    {
      "phrase": "perovskite solar cells",
      "abbr": "PSCs"
    },
    {
      "phrase": "quantitative structure-property relationship",
      "abbr": "QSPR"
    }
  ],
  "script": "check_abbreviation_after_definition.py",
  "description": "Use when checking or fixing DOCX abbreviation consistency after first definition, such as using ML after machine learning has been defined.",
  "display_name": "DOCX Abbreviation After Definition"
}

@dataclass
class Finding:
    kind: str
    paragraph_index: int
    anchor: str
    message: str
    old: str | None = None
    new: str | None = None
    category: str = ""

def qn(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}"

def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def para_text(p: ET.Element) -> str:
    return norm("".join(n.text or "" for n in p.iter() if n.tag in {qn(W_NS,'t'), qn(W_NS,'delText'), qn(M_NS,'t')}))

def load_parts(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        return {i.filename: z.read(i.filename) for i in z.infolist()}

def max_word_id(root: ET.Element) -> int:
    vals=[]
    for el in root.iter():
        v=el.get(qn(W_NS,'id'))
        if v and v.isdigit(): vals.append(int(v))
    return max(vals, default=0)

def parent_map(root: ET.Element):
    return {c:p for p in root.iter() for c in list(p)}

def clone_run(template: ET.Element|None, text: str, tag: str='t') -> ET.Element:
    r=ET.Element(qn(W_NS,'r'))
    if template is not None:
        rpr=template.find('w:rPr', NS)
        if rpr is not None: r.append(copy.deepcopy(rpr))
    t=ET.Element(qn(W_NS, tag)); t.text=text; r.append(t); return r

def apply_replace(p: ET.Element, old: str, new: str, change_id: int, author: str, date: str) -> bool:
    if not old or old == new: return False
    parents=parent_map(p)
    for t_el in p.findall('.//w:t', NS):
        txt=t_el.text or ''
        if old not in txt: continue
        run=t_el
        while run is not None and run.tag != qn(W_NS,'r'):
            run=parents.get(run)
        cont=parents.get(run) if run is not None else None
        if run is None or cont is None: continue
        before, after = txt.split(old, 1)
        pieces=[]
        if before: pieces.append(clone_run(run,before))
        d=ET.Element(qn(W_NS,'del'), {qn(W_NS,'id'):str(change_id), qn(W_NS,'author'):author, qn(W_NS,'date'):date})
        d.append(clone_run(run, old, 'delText'))
        ins=ET.Element(qn(W_NS,'ins'), {qn(W_NS,'id'):str(change_id+1), qn(W_NS,'author'):author, qn(W_NS,'date'):date})
        ins.append(clone_run(run, new))
        pieces.extend([d, ins])
        if after: pieces.append(clone_run(run, after))
        idx=list(cont).index(run); cont.remove(run)
        for off,node in enumerate(pieces): cont.insert(idx+off,node)
        return True
    full=para_text(p)
    if old not in full: return False
    runs=[c for c in list(p) if c.tag == qn(W_NS,'r')]
    if not runs: return False
    template=runs[0]; before, after=full.split(old,1); pieces=[]
    if before: pieces.append(clone_run(template,before))
    d=ET.Element(qn(W_NS,'del'), {qn(W_NS,'id'):str(change_id), qn(W_NS,'author'):author, qn(W_NS,'date'):date}); d.append(clone_run(template,old,'delText'))
    ins=ET.Element(qn(W_NS,'ins'), {qn(W_NS,'id'):str(change_id+1), qn(W_NS,'author'):author, qn(W_NS,'date'):date}); ins.append(clone_run(template,new))
    pieces.extend([d,ins])
    if after: pieces.append(clone_run(template,after))
    first=list(p).index(runs[0])
    for r in runs: p.remove(r)
    for off,node in enumerate(pieces): p.insert(first+off,node)
    return True

def w_el(name: str, attrs=None, text=None):
    el=ET.Element(qn(W_NS,name), attrs or {})
    if text is not None: el.text=text
    return el

def ensure_comments_root(parts):
    if 'word/comments.xml' in parts: return ET.fromstring(parts['word/comments.xml'])
    return ET.Element(qn(W_NS,'comments'))

def append_comment(root, cid, text, author, date):
    c=w_el('comment',{qn(W_NS,'id'):str(cid), qn(W_NS,'author'):author, qn(W_NS,'date'):date, qn(W_NS,'initials'):'AI'})
    p=w_el('p'); r=w_el('r'); r.append(w_el('t', text=text)); p.append(r); c.append(p); root.append(c)

def add_comment_markers(p, cid):
    children=list(p); idxs=[i for i,c in enumerate(children) if c.tag == qn(W_NS,'r')]
    if idxs: first=idxs[0]
    else: first=0
    start=w_el('commentRangeStart',{qn(W_NS,'id'):str(cid)}); end=w_el('commentRangeEnd',{qn(W_NS,'id'):str(cid)})
    ref=w_el('r'); rpr=w_el('rPr'); rpr.append(w_el('rStyle',{qn(W_NS,'val'):'CommentReference'})); ref.append(rpr); ref.append(w_el('commentReference',{qn(W_NS,'id'):str(cid)}))
    p.insert(first,start); p.append(end); p.append(ref); return True

def ensure_comment_plumbing(parts, comments_root):
    rels=ET.fromstring(parts['word/_rels/document.xml.rels'])
    exists=False
    for rel in rels.findall(f'{{{PKG_REL_NS}}}Relationship'):
        if rel.get('Type') == COMMENTS_REL_TYPE and rel.get('Target') == 'comments.xml': exists=True
    if not exists:
        nums=[int(r.get('Id','rId0')[3:]) for r in rels.findall(f'{{{PKG_REL_NS}}}Relationship') if r.get('Id','').startswith('rId') and r.get('Id','')[3:].isdigit()]
        rels.append(ET.Element(qn(PKG_REL_NS,'Relationship'), {'Id':f'rId{max(nums, default=0)+1}', 'Type':COMMENTS_REL_TYPE, 'Target':'comments.xml'}))
    ct=ET.fromstring(parts['[Content_Types].xml'])
    if not any(o.get('PartName') == '/word/comments.xml' for o in ct.findall(f'{{{CT_NS}}}Override')):
        ct.append(ET.Element(qn(CT_NS,'Override'), {'PartName':'/word/comments.xml','ContentType':COMMENTS_CONTENT_TYPE}))
    parts['word/comments.xml']=ET.tostring(comments_root, encoding='utf-8', xml_declaration=True)
    parts['word/_rels/document.xml.rels']=ET.tostring(rels, encoding='utf-8', xml_declaration=True)
    parts['[Content_Types].xml']=ET.tostring(ct, encoding='utf-8', xml_declaration=True)

def ensure_track(parts):
    if 'word/settings.xml' not in parts: return
    root=ET.fromstring(parts['word/settings.xml'])
    if root.find('w:trackRevisions', NS) is None:
        root.append(w_el('trackRevisions'))
    parts['word/settings.xml']=ET.tostring(root, encoding='utf-8', xml_declaration=True)

def is_caption(text):
    return re.match(r'^(?:Fig\.|Figure|Supplementary Fig\.|Supplementary Figure)\s+\d+\s*\|', text, re.I)

def in_references_state(text, active):
    if re.fullmatch(r'(references|bibliography)', text, re.I): return True
    return active

def detect(paras):
    findings=[]; mode=CONFIG['mode']; ref_active=False; seen_defs={}
    for i,p in enumerate(paras):
        text=para_text(p); low=text.lower()
        if not text: continue
        ref_active=in_references_state(text, ref_active)
        if mode == 'replacements':
            for item in CONFIG.get('replacements',[]):
                old=item['old']; new=item['new']
                if old in text:
                    findings.append(Finding('replace',i,text[:220],item.get('message',f'Replace {old} with {new}.'),old,new,item.get('category','replacement')))
            for item in CONFIG.get('regex_replacements',[]):
                for m in re.finditer(item['pattern'], text):
                    old=m.group(0); new=item.get('replacement','{match}').replace('{match}', old)
                    if item.get('scientific'):
                        base, exp = re.split('e', old, flags=re.I); new=f'{base} x 10^{int(exp)}'
                    findings.append(Finding('replace',i,text[:220],item.get('message','Normalize this expression.'),old,new,item.get('category','regex')))
        elif mode == 'abbrev':
            if ref_active:
                continue
            for item in CONFIG['definitions']:
                phrase=item['phrase']; abbr=item['abbr']
                if phrase.lower()+f' ({abbr.lower()})' in low: seen_defs[phrase.lower()]=abbr
                elif phrase.lower() in low and phrase.lower() in seen_defs:
                    findings.append(Finding('replace',i,text[:220],f'Use {abbr} after it has been defined.', phrase, abbr, 'abbreviation'))
        elif mode == 'comments':
            for item in CONFIG.get('comment_rules',[]):
                scope=item.get('scope','all')
                if scope == 'caption' and not is_caption(text): continue
                if scope == 'references' and not ref_active: continue
                if scope == 'not_references' and ref_active: continue
                matched=False
                if 'contains' in item: matched=all(s.lower() in low for s in item['contains'])
                if 'any_contains' in item: matched=any(s.lower() in low for s in item['any_contains'])
                if 'regex' in item: matched=re.search(item['regex'], text, re.I) is not None
                if 'min_words' in item: matched=len(text.split()) >= item['min_words']
                if matched:
                    findings.append(Finding('comment',i,text[:220],item['message'],None,None,item.get('category','comment')))
    return unique(findings)

def unique(findings):
    seen=set(); out=[]
    for f in findings:
        key=(f.kind,f.paragraph_index,f.message,f.old,f.new)
        if key not in seen:
            seen.add(key); out.append(f)
    return out

def write_docx(parts, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True); tmp=out_path.with_suffix(out_path.suffix+'.tmp')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
        for n,d in parts.items(): z.writestr(n,d)
    shutil.move(tmp,out_path)

def main():
    ap=argparse.ArgumentParser(description=CONFIG['description'])
    ap.add_argument('docx', type=Path); ap.add_argument('--report', type=Path); ap.add_argument('--apply', action='store_true'); ap.add_argument('--out', type=Path); ap.add_argument('--author', default=CONFIG['display_name'])
    ap.add_argument('--protect', action='append', default=[])
    args=ap.parse_args(); path=args.docx.expanduser().resolve(); parts=load_parts(path); doc=ET.fromstring(parts['word/document.xml']); paras=doc.findall('.//w:p', NS)
    findings=detect(paras); applied=0; comments=0
    if args.apply:
        if not args.out: raise SystemExit('--out is required with --apply')
        now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
        cid=max_word_id(doc)+1; change_id=max_word_id(doc)+1000; comments_root=ensure_comments_root(parts)
        for f in findings:
            p=paras[f.paragraph_index]
            if f.kind == 'replace' and f.old and f.new and apply_replace(p,f.old,f.new,change_id,args.author,now): applied += 1; change_id += 2
            elif f.kind == 'comment': append_comment(comments_root,cid,f.message,args.author,now); add_comment_markers(p,cid); cid += 1; comments += 1
        parts['word/document.xml']=ET.tostring(doc, encoding='utf-8', xml_declaration=True)
        if comments: ensure_comment_plumbing(parts, comments_root)
        if applied: ensure_track(parts)
        write_docx(parts, args.out.expanduser().resolve())
    payload={'file':str(path),'skill':CONFIG['name'],'finding_count':len(findings),'tracked_replacements_applied':applied,'comments_applied':comments,'findings':[asdict(f) for f in findings]}
    data=json.dumps(payload, indent=2, ensure_ascii=False)
    if args.report: args.report.expanduser().resolve().write_text(data+'\n', encoding='utf-8')
    else: print(data)
if __name__ == '__main__': main()
