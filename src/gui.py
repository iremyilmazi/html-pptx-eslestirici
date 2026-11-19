"""Offline CSV review UI using standard-library Tkinter."""
import argparse
import csv
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path


def read(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f, delimiter=';')
        return r.fieldnames, list(r)


class Reviewer(tk.Tk):
    def __init__(self, mapping, inventory):
        super().__init__()
        self.mapping = Path(mapping)
        self.fields, self.rows = read(mapping)
        _, self.inventory = read(inventory)
        self.title('HTML → PPTX | Yerel eşleştirme kontrolü')
        self.geometry('1200x760')
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.changed = False
        top = ttk.Frame(self, padding=9); top.pack(fill='x')
        ttk.Label(top, text='Filtre:').pack(side='left')
        self.filter = ttk.Combobox(top, values=['Tümü','Onaysız','Düşük / eşleşmedi','Orta','Yüksek','Onaylı'], state='readonly', width=22)
        self.filter.set('Onaysız'); self.filter.pack(side='left', padx=8)
        self.filter.bind('<<ComboboxSelected>>', lambda _: self.refresh())
        ttk.Button(top, text='Kaydet (Ctrl+S)', command=self.save).pack(side='right')
        self.bind('<Control-s>', lambda _: self.save())
        self.summary = ttk.Label(top, text=''); self.summary.pack(side='right', padx=12)
        frame = ttk.Frame(self, padding=8); frame.pack(fill='both', expand=True)
        cols = ('html_id','html_type','confidence','suggested_slide','target_slide','target_shape_id','apply','translation')
        self.tree = ttk.Treeview(frame, columns=cols, show='headings', selectmode='browse', height=16)
        for c in cols:
            self.tree.heading(c,text=c)
            self.tree.column(c,width=95 if c!='translation' else 470, stretch=(c=='translation'))
        y=ttk.Scrollbar(frame,orient='vertical',command=self.tree.yview)
        self.tree.configure(yscrollcommand=y.set); self.tree.pack(side='left',fill='both',expand=True); y.pack(side='right',fill='y')
        self.tree.bind('<<TreeviewSelect>>', self.selected)
        edit=ttk.LabelFrame(self, text='Seçilen eşleşme (1 tabanlı slayt, tablo satır/sütunu)', padding=10)
        edit.pack(fill='x',padx=10,pady=8)
        self.source=tk.Text(edit,height=3,wrap='word');self.source.grid(row=0,column=0,columnspan=4,sticky='ew',pady=3)
        self.target=tk.Text(edit,height=3,wrap='word');self.target.grid(row=1,column=0,columnspan=4,sticky='ew',pady=3)
        self.target.configure(state='disabled');edit.columnconfigure(3,weight=1)
        self.vars={}
        for j, key in enumerate(['target_slide','target_shape_id','target_row','target_col']):
            cell=ttk.Frame(edit);cell.grid(row=2,column=j,sticky='w',padx=8,pady=6)
            ttk.Label(cell,text=key).pack(anchor='w')
            v=tk.StringVar(); self.vars[key]=v
            ttk.Entry(cell,textvariable=v,width=14).pack()
        ttk.Button(edit,text='Hedefi önizle',command=self.preview).grid(row=3,column=0,pady=8)
        ttk.Button(edit,text='Hedefi kaydet',command=self.update).grid(row=3,column=1,pady=8)
        ttk.Button(edit,text='Onayla',command=lambda:self.approve(True)).grid(row=3,column=2,pady=8)
        ttk.Button(edit,text='Onayı kaldır',command=lambda:self.approve(False)).grid(row=3,column=3,pady=8)
        ttk.Label(edit,text='Öneriler yalnızca yardımcıdır; onaylanmayan satırlar PPTX\'e yazılmaz. Kaydetmeden kapatmayın.').grid(row=4,column=0,columnspan=4,sticky='w')
        self.current=None
        self.refresh()

    def visible(self, row):
        f=self.filter.get(); approved=row.get('apply','').strip().casefold() in ('evet','yes','true','1')
        return (f=='Tümü' or (f=='Onaysız' and not approved) or (f=='Onaylı' and approved)
                or (f=='Düşük / eşleşmedi' and row.get('confidence') in ('dusuk','eslesmedi'))
                or (f=='Orta' and row.get('confidence')=='orta') or (f=='Yüksek' and row.get('confidence')=='yuksek'))

    def refresh(self, keep=None):
        self.tree.delete(*self.tree.get_children())
        for i,row in enumerate(self.rows):
            if self.visible(row):
                self.tree.insert('', 'end', iid=str(i), values=[row.get(c,'')[:110] if c=='translation' else row.get(c,'') for c in self.tree['columns']])
        approved=sum(row.get('apply','').casefold()=='evet' for row in self.rows)
        self.summary.configure(text=f'{approved}/{len(self.rows)} onaylandı')
        if keep is not None and self.tree.exists(str(keep)):
            self.tree.selection_set(str(keep));self.tree.see(str(keep))

    def selected(self,_=None):
        selection=self.tree.selection()
        if not selection:return
        i=int(selection[0]);self.current=i
        row=self.rows[i]
        self.source.delete('1.0','end');self.source.insert('1.0',row.get('translation',''))
        for key,v in self.vars.items():v.set(row.get(key,''))
        self.preview()

    def preview(self):
        try:slide=int(self.vars['target_slide'].get());sid=int(self.vars['target_shape_id'].get())
        except ValueError: text='Hedef slayt ve shape ID seçilmedi.'
        else:
            targets=[r for r in self.inventory if int(r['slide'])==slide and int(r['shape_id'])==sid]
            text=targets[0]['text'] if targets else 'Bu hedef envanterde bulunamadı.'
        self.target.configure(state='normal');self.target.delete('1.0','end');self.target.insert('1.0',text);self.target.configure(state='disabled')

    def update(self):
        if self.current is None:return False
        row=self.rows[self.current]
        vals={k:v.get().strip() for k,v in self.vars.items()}
        try:
            slide=int(vals['target_slide']);sid=int(vals['target_shape_id'])
            target=next(x for x in self.inventory if int(x['slide'])==slide and int(x['shape_id'])==sid)
            is_table=target['kind']=='table'
            if is_table!=(row.get('html_type')=='table_cell'):
                raise ValueError('HTML bloğu ile PPTX hedefinin tablo/metin türü uyuşmuyor.')
            if is_table and (int(vals['target_row'])<1 or int(vals['target_col'])<1):
                raise ValueError('Tablo hücresinde satır/sütun pozitif olmalı.')
            if not is_table:vals['target_row']='';vals['target_col']=''
        except (ValueError,StopIteration) as e:
            messagebox.showerror('Hedef hatası',str(e));return False
        row.update(vals);self.changed=True;self.refresh(self.current)
        return True

    def approve(self, yes):
        if self.current is None:return
        if yes and not self.update():return
        row=self.rows[self.current]
        key=(row['target_slide'],row['target_shape_id'],row['target_row'],row['target_col'])
        if yes and any(r is not row and r.get('apply','').casefold()=='evet' and
                       (r.get('target_slide'),r.get('target_shape_id'),r.get('target_row'),r.get('target_col'))==key for r in self.rows):
            messagebox.showerror('Çakışma','Bu hedef başka bir satır için onaylanmış.');return
        row['apply']='EVET' if yes else ''
        self.changed=True;self.refresh(self.current)

    def save(self):
        with self.mapping.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=self.fields,extrasaction='ignore',delimiter=';');writer.writeheader();writer.writerows(self.rows)
        self.changed=False
        messagebox.showinfo('Kaydedildi',str(self.mapping))

    def on_close(self):
        if self.changed and not messagebox.askyesno('Kaydedilmemiş değişiklikler','Kaydetmeden çıkılsın mı?'):
            return
        self.destroy()

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--mapping',default='cikti/eslestirme_sablonu.csv')
    p.add_argument('--inventory',default='cikti/pptx_envanter.csv')
    args=p.parse_args();Reviewer(args.mapping,args.inventory).mainloop()
