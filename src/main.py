"""Yerel, internetsiz HTML -> mevcut PPTX metin eşleştirme yardımcısı."""
import argparse
import csv
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag
from pptx import Presentation
from auto_match import flat_slots, suggest

FIELDS = ['html_id','html_file','html_type','translation','suggested_slide','suggested_shape_id','suggested_target','confidence','match_score','target_slide','target_shape_id','target_row','target_col','apply','note']

def normalize(s):
    return re.sub(r'\s+', ' ', s or '').strip()

def html_text(tag):
    # <br> içindeki yeni satırlar korunur; <strong> metni aynı blokta kalır.
    soup = BeautifulSoup(str(tag), 'html.parser')
    for br in soup.find_all('br'):
        br.replace_with('\n')
    return '\n'.join(normalize(line) for line in soup.get_text().splitlines() if normalize(line))

def parse_html(files):
    blocks=[]
    for path in files:
        soup=BeautifulSoup(Path(path).read_text(encoding='utf-8-sig'), 'html.parser')
        root=soup.body or soup
        # Tabloları tek kaynak birimi olarak tut: hedefteki tablo yapısı farklı olabilir.
        for tag in root.find_all(['p','h1','h2','h3','h4','h5','h6','table'], recursive=True):
            if tag.find_parent('table') and tag.name!='table':
                continue
            if tag.name=='table':
                for ri,tr in enumerate(tag.find_all('tr'),1):
                    for ci,cell in enumerate(tr.find_all(['td','th'],recursive=False),1):
                        value=html_text(cell)
                        if value:
                            blocks.append({'html_id':f'H{len(blocks)+1:04}', 'html_file':Path(path).name,
                                           'html_type':'table_cell','translation':value,
                                           'source_row':ri,'source_col':ci})
                continue
            value=html_text(tag)
            if not value: continue
            blocks.append({'html_id':f'H{len(blocks)+1:04}', 'html_file':Path(path).name,
                           'html_type':tag.name,'translation':value})
    return blocks

def slides_inventory(pptx):
    prs=Presentation(str(pptx)); slots=[]
    for i, slide in enumerate(prs.slides,1):
        for shape in sorted(slide.shapes,key=lambda s:(round(s.top/914400,2),round(s.left/914400,2))):
            if shape.has_table:
                summary=[]
                for row in shape.table.rows:
                    summary.append(' / '.join(normalize(c.text) for c in row.cells))
                slots.append({'slide':i,'shape_id':shape.shape_id,'kind':'table','text':' | '.join(summary)})
            elif shape.has_text_frame and normalize(shape.text):
                slots.append({'slide':i,'shape_id':shape.shape_id,'kind':'text','text':shape.text})
    return prs,slots

def write_csv(path, fields, rows):
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',delimiter=';')
        writer.writeheader(); writer.writerows(rows)

def read_csv(path):
    with open(path,encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f,delimiter=';'))

def command_prepare(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    htmls=sorted(Path(args.html_dir).glob('*.html'))+sorted(Path(args.html_dir).glob('*.htm'))
    if not htmls: raise ValueError('HTML klasöründe .html veya .htm bulunamadı.')
    blocks=parse_html(htmls)
    prs, slots=slides_inventory(args.pptx)
    write_csv(out/'pptx_envanter.csv',['slide','shape_id','kind','text'],slots)
    write_csv(out/'html_bloklar.csv',['html_id','html_file','html_type','translation'],blocks)
    # Sıra, rakam, uzunluk ve içerik benzerliğini kullanır. Güven skoru olasılık değildir.
    auto_slots=flat_slots(prs)
    candidates=suggest(blocks,auto_slots)
    template=[]
    for idx,b in enumerate(blocks):
        info=candidates.get(idx)
        suggestion, confidence, score=info if info else (None,'eslesmedi','')
        template.append({**b,
                         'suggested_slide':suggestion['slide'] if suggestion else '',
                         'suggested_shape_id':suggestion['shape_id'] if suggestion else '',
                         'suggested_target':normalize(suggestion['text'])[:120] if suggestion else '',
                         'confidence':confidence,'match_score':score,
                         'target_slide':suggestion['slide'] if suggestion else '',
                         'target_shape_id':suggestion['shape_id'] if suggestion else '',
                         'target_row':suggestion['row'] if suggestion else '',
                         'target_col':suggestion['col'] if suggestion else '',
                         'apply':'','note':('Otomatik öneri; kontrol edip onaylayın' if suggestion else 'Hedef bulunamadı')})
    write_csv(out/'eslestirme_sablonu.csv',FIELDS,template)
    print(f'{len(prs.slides)} slayt, {len(slots)} metin/tablo alanı, {len(blocks)} HTML bloğu.')
    print('Öneri oluşturuldu; hiçbir eşleşme otomatik ONAYLANMAZ. gui.py ile inceleyin veya CSV apply=EVET girin.')

def replace_text_preserve(shape, new_text):
    # İlk run'ın biçimini koruyup metni ona yazar. Diğer run'ları boşaltır.
    # Farklı run biçimleri tek alanda birleştirildiğinde biçim kısmen kaybolabilir.
    tf=shape.text_frame
    pars=tf.paragraphs
    if not pars:
        shape.text=new_text;return
    first=pars[0]
    if not first.runs:
        first.text=new_text
    else:
        first.runs[0].text=new_text
        for run in first.runs[1:]: run.text=''
    for p in pars[1:]:
        for r in p.runs:r.text=''
    # Yeni satırları var olan run içerisinde koruma; PPTX satır sonları görüntülenir.

def command_apply(args):
    rows=read_csv(args.mapping)
    prs,slots=slides_inventory(args.pptx)
    targets={(s['slide'],s['shape_id']):s for s in slots}
    updated=set(); errors=[]; applied=0
    for n,row in enumerate(rows,2):
        if normalize(row.get('apply','')).casefold() not in ('evet','yes','true','1'):
            continue
        try:
            slide=int(row['target_slide']);sid=int(row['target_shape_id'])
            key=(slide,sid)
            if key not in targets:raise ValueError('Hedef shape bulunamadı.')
            if (key, row.get('target_row',''),row.get('target_col','')) in updated:raise ValueError('Aynı hedef/hücre birden çok kez seçilmiş.')
            shape=next(s for s in prs.slides[slide-1].shapes if s.shape_id==sid)
            value=row['translation']
            if targets[key]['kind']=='table':
                if row['html_type']!='table_cell':
                    raise ValueError('Tablo hedefi için HTML tablosunun tek hücresi gerekir.')
                ri=int(row['target_row'])-1; ci=int(row['target_col'])-1
                if ri<0 or ri>=len(shape.table.rows) or ci<0 or ci>=len(shape.table.columns):
                    raise ValueError('Tablo hücre satır/sütun indeksi geçersiz.')
                # Birleştirilmiş hücreleri sessizce ezme.
                cell=shape.table.cell(ri,ci)
                if cell.is_spanned:
                    raise ValueError('Birleştirilmiş tablonun kaplanan hücresi seçilmiş.')
                replace_text_preserve(cell,value)
            else:
                if row['html_type']=='table_cell':
                    raise ValueError('HTML tablo hücresi PPTX metin kutusuna eşlenemez.')
                if row.get('target_row','') or row.get('target_col',''):
                    raise ValueError('Metin kutusunda target_row / target_col boş olmalıdır.')
                replace_text_preserve(shape,value)
            updated.add((key,row.get('target_row',''),row.get('target_col','')));applied+=1
        except Exception as e:errors.append(f'Satır {n} ({row.get("html_id", "?")}): {e}')
    if errors:
        report=Path(args.output).with_suffix('.hatalar.txt');report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text('\n'.join(errors),encoding='utf-8')
        print(f'{len(errors)} sorun bulundu: {report}',file=sys.stderr)
        # Hata varsa sunum kaydedilmez; kısmi yazma yapılmaz.
        return 2
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    prs.save(args.output)
    print(f'{applied} metin alanı güncellendi -> {args.output}')
    print('PowerPoint üzerinde taşma, yazı biçimi ve animasyonları gözle kontrol edin.')
    return 0

def main(argv=None):
    ap=argparse.ArgumentParser(description='HTML çevirilerini mevcut PPTX ile yerel eşleştirme')
    sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('hazirla');p.add_argument('--pptx',required=True);p.add_argument('--html-dir',required=True);p.add_argument('--output',default='cikti');p.set_defaults(func=command_prepare)
    p=sub.add_parser('uygula');p.add_argument('--pptx',required=True);p.add_argument('--mapping',required=True);p.add_argument('--output',default='cikti/cevrilmis.pptx');p.set_defaults(func=command_apply)
    args=ap.parse_args(argv)
    try:return args.func(args)
    except Exception as e:print('HATA:',e,file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
