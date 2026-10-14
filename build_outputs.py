#!/usr/bin/env python3
"""Assemble verified SIM800-family extraction JSONs into deliverables."""
from pathlib import Path
import csv, json, shutil, hashlib, re

ROOT = Path('/home/ubuntu/sim800_datasheet_project')
RAW = ROOT / 'agent_output'
OUT = ROOT / 'output' / '2026-10-14'
MODELS = ['SIM800L','SIM800C','SIM808','SIM868','SIM800A','SIM800F','SIM800H','SIM800','SIM800C-DS']
SPEC_ALIASES = {
 'operating_voltage':['operating_voltage'], 'current_consumption':['current_consumption','current_consumption_consumption_modes','consumption_modes'],
 'frequency_bands':['frequency_bands'], 'dimensions':['dimensions','dimensions_mm'], 'weight':['weight'],
 'operating_temperature':['operating_temperature'], 'package_type':['package_type'],
 'sim_card_type':['sim_card_type','SIM_card_type'], 'gnss_gps_support':['gnss_gps_support','GNSS_GPS_support'],
 'bluetooth_support':['bluetooth_support','bluetooth','Bluetooth'], 'gprs_class':['gprs_class','GPRS_class'], 'data_rate':['data_rate']
}

def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def dump_json(path, value): Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def as_items(value): return [] if value is None else value if isinstance(value,list) else [value]
def csv_write(path, header, rows):
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=header,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
def compact_json(v): return json.dumps(v,ensure_ascii=False,separators=(',',':'))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    modules={}
    for model in MODELS:
        p=RAW/'modules'/f'{model}.json'
        if not p.exists(): raise SystemExit(f'Missing module output: {p}')
        modules[model]=read_json(p)
    catalog=read_json(RAW/'shared_at_command_catalog.json')
    manifest=read_json(ROOT/'source_manifest.json')
    source_map={}
    for doc in manifest['documents']:
        pdf=doc['source_pdf']; source_map[Path(pdf).stem.lower()]=pdf
        source_map[Path(pdf).name.lower()]=pdf
    def normalize_tree(x):
        if isinstance(x,dict):
            for key in ('source','citation'):
                ref=x.get(key)
                if isinstance(ref,dict) and isinstance(ref.get('source_pdf'),str):
                    old=ref['source_pdf']; stem=Path(old).stem.lower()
                    ref['source_pdf']=source_map.get(old.lower(),source_map.get(stem,old))
            for v in x.values(): normalize_tree(v)
        elif isinstance(x,list):
            for v in x: normalize_tree(v)
    for d in modules.values(): normalize_tree(d)
    normalize_tree(catalog)

    root={'schema_version':'1.0.0','extraction_date':'2026-10-14','repository':manifest['repository'],'repository_commit':manifest['commit'],'source_manifest':manifest,'shared_at_command_catalog':catalog,'modules':modules}
    dump_json(OUT/'sim800_datasheets.json',root)
    (OUT/'modules').mkdir(exist_ok=True)
    for model,data in modules.items(): dump_json(OUT/'modules'/f'{model}.json',data)
    dump_json(OUT/'shared_at_command_catalog.json',catalog); dump_json(OUT/'source_manifest.json',manifest)

    def refs(value):
        found=[]
        def walk(x):
            if isinstance(x,dict):
                for key in ('source','citation'):
                    r=x.get(key)
                    if isinstance(r,dict) and r.get('source_pdf'):
                        pages=r.get('pages',r.get('physical_pages',[]))
                        found.append((r.get('source_pdf',''),pages,r.get('locator','')))
                for k,v in x.items():
                    if k not in ('source','citation'): walk(v)
            elif isinstance(x,list):
                for y in x: walk(y)
        walk(value)
        return found
    def first_ref(value):
        rr=refs(value)
        return rr[0] if rr else ('',[],'')
    def val_of(x): return x.get('value') if isinstance(x,dict) and 'value' in x else x
    def stringify(x): return '' if x is None else x if isinstance(x,str) else compact_json(x)

    # Specifications: long form, one row per reported value, null rows retained.
    spec_rows=[]
    for model,data in modules.items():
        specs=data.get('technical_specs') or {}
        for canonical,aliases in SPEC_ALIASES.items():
            raw=None
            for alias in aliases:
                if alias in specs: raw=specs[alias]; break
            entries=as_items(raw)
            if not entries:
                spec_rows.append({'module':model,'field':canonical,'value':'null','unit':'','source_pdf':'','pages':'','notes':'See module missing_data; not found/recorded'})
            for item in entries:
                src,pages,_=first_ref(item)
                unit=item.get('unit','') if isinstance(item,dict) else ''
                val=val_of(item)
                notes=item.get('notes','') if isinstance(item,dict) else ''
                spec_rows.append({'module':model,'field':canonical,'value':stringify(val),'unit':unit,'source_pdf':src,'pages':compact_json(pages) if isinstance(pages,(list,dict)) else pages,'notes':notes})
    csv_write(OUT/'specs.csv',['module','field','value','unit','source_pdf','pages','notes'],spec_rows)

    # AT command rows use detailed actual catalog fields, preserving source blocks as JSON strings.
    command_rows=[]
    for c in as_items(catalog.get('commands')):
        if not isinstance(c,dict): command_rows.append({'command':str(c)}); continue
        src,pages,loc=first_ref(c.get('heading',c))
        purpose=val_of(c.get('purpose',''))
        command_rows.append({'command':c.get('command',''),'section':c.get('section',''),'purpose':stringify(purpose),'execution_forms':compact_json(c.get('documented_execution_forms',[])),'parameters':compact_json(c.get('parameter_definitions',[])),'responses_output_parameters':compact_json(c.get('responses_output_parameters',[])),'examples':compact_json(c.get('examples',[])),'versions':'V1.12 primary; see version_differences for edition coverage','source_pdf':src,'pages':compact_json(pages) if isinstance(pages,(list,dict)) else pages,'locator':loc,'raw_section_excerpt':compact_json(c.get('raw_section_excerpt',{})),'ambiguity':c.get('ambiguity','')})
    csv_write(OUT/'at_commands.csv',['command','section','purpose','execution_forms','parameters','responses_output_parameters','examples','versions','source_pdf','pages','locator','raw_section_excerpt','ambiguity'],command_rows)

    # Tests: retain every category row and criteria precisely as documented.
    test_rows=[]; categories=['functional','communication','power','environmental']
    for model,data in modules.items():
        tests=data.get('validation_tests') or {}
        for category in categories:
            rows=as_items(tests.get(category))
            if not rows: test_rows.append({'module':model,'category':category,'test':'','method':'','acceptance_criteria':'null','source_pdf':'','pages':'','notes':'No test record extracted; see missing_data'})
            for t in rows:
                if not isinstance(t,dict): t={'test':str(t)}
                src,pages,_=first_ref(t)
                test_rows.append({'module':model,'category':category,'test':stringify(t.get('test','')),'method':stringify(t.get('method/procedure',t.get('method',t.get('procedure','')))),'acceptance_criteria':stringify(t.get('explicit_pass_fail_criteria',t.get('acceptance_criteria'))),'source_pdf':src,'pages':compact_json(pages) if isinstance(pages,(list,dict)) else pages,'notes':stringify(t.get('notes',''))})
    csv_write(OUT/'tests.csv',['module','category','test','method','acceptance_criteria','source_pdf','pages','notes'],test_rows)

    def compact_spec(specs,canonical):
        for alias in SPEC_ALIASES[canonical]:
            if alias in specs:
                values=[]
                for item in as_items(specs[alias]):
                    v=val_of(item)
                    if v is not None: values.append(stringify(v)+((' '+item.get('unit','')) if isinstance(item,dict) and item.get('unit') else ''))
                return '; '.join(values) if values else '—'
        return '—'
    order=['frequency_bands','operating_voltage','dimensions','weight','operating_temperature','package_type','sim_card_type','gnss_gps_support','bluetooth_support','gprs_class','data_rate']
    labels={'frequency_bands':'Bands','operating_voltage':'Supply voltage','dimensions':'Dimensions','weight':'Weight','operating_temperature':'Operating temperature','package_type':'Package','sim_card_type':'SIM','gnss_gps_support':'GNSS/GPS','bluetooth_support':'Bluetooth','gprs_class':'GPRS class','data_rate':'Data rate'}
    lines=['# SIM800 family datasheet differences','',f"Source: [{manifest['repository']}]({manifest['repository']}) at commit `{manifest['commit']}`. Values are transcribed from cited module PDFs; `—` means not found in the supplied source, not that the capability is absent.",'','| Module | '+' | '.join(labels[k] for k in order)+' |','|---|'+'---|'*len(order)]
    for model,data in modules.items():
        specs=data.get('technical_specs') or {}; vals=[compact_spec(specs,k) for k in order]
        lines.append('| '+model+' | '+' | '.join(v.replace('|','\\|').replace('\n',' ') for v in vals)+' |')
    lines += ['', '## Interpretation notes','', '- Family-level AT command support is recorded in `shared_at_command_catalog.json`; it is not a claim of support by every model.', '- Each per-model JSON contains pinout, reference circuits, PCB/antenna/protection guidance, validation details, missing fields, ambiguities, and page citations.', '- Empty or null values mean the supplied source did not establish the requested fact; they do not mean the capability is absent.']
    (OUT/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

    # Citation audit supports pages/physical_pages and both PDF name and legacy extracted-text stems.
    valid_sources={doc['source_pdf']:doc['pages'] for doc in manifest['documents']}
    valid_stems={Path(name).stem.lower(): (name,pages) for name,pages in valid_sources.items()}
    problems=[]; missing_lines=[]; citation_count=0
    def audit(value, label):
        nonlocal citation_count
        if isinstance(value,dict):
            for key in ('source','citation'):
                r=value.get(key)
                if isinstance(r,dict) and r.get('source_pdf'):
                    citation_count+=1; rawname=r['source_pdf']; name=rawname if rawname in valid_sources else valid_stems.get(Path(rawname).stem.lower(),(None,None))[0]
                    pages=r.get('pages',r.get('physical_pages'))
                    if name is None: problems.append(f'{label}: unknown source_pdf {rawname!r}')
                    if pages is None or pages==[]: problems.append(f'{label}: citation has no page number')
                    if name:
                        nums=pages if isinstance(pages,list) else [pages]
                        for n in nums:
                            try: n=int(n)
                            except Exception: problems.append(f'{label}: nonnumeric page {n!r}'); continue
                            if n<1 or n>valid_sources[name]: problems.append(f'{label}: page {n} outside {name} range 1..{valid_sources[name]}')
            for k,v in value.items():
                if k not in ('source','citation'): audit(v,label+'.'+k)
        elif isinstance(value,list):
            for i,v in enumerate(value): audit(v,f'{label}[{i}]')
    for model,data in modules.items():
        for x in as_items(data.get('missing_data')): missing_lines.append(f'- **{model}:** {stringify(x)}')
        audit(data,model)
    for x in as_items(catalog.get('missing_data')): missing_lines.append(f'- **AT catalog:** {stringify(x)}')
    audit(catalog,'AT catalog')
    diff=as_items(catalog.get('version_differences'))
    version_sections=[]
    for model,data in modules.items():
        differences=as_items(data.get('version_differences'))
        if differences: version_sections.append(f'### {model}\n\n'+'\n'.join('- '+stringify(x) for x in differences))
    lines=['# Validation report','',f"- Repository snapshot: `{manifest['commit']}`",f"- PDFs ingested: {manifest['pdf_count']}; physical pages: {manifest['total_pages']}",'- Extracted page-text coverage: every PDF page produced non-empty text in the initial page-count audit.',f'- Citation references checked: {citation_count}',f'- Citation integrity errors: {len(problems)}','', '## Missing data and coverage limitations','']
    lines += missing_lines or ['- No missing-data entries emitted; inspect module JSON directly.']
    lines += ['', '## AT-manual version comparison','',f'- Revision comparison contains {len(diff)} recorded version-difference/coverage entries.']
    # Persistent known parser note supplied by the AT catalog workflow.
    for note in as_items(catalog.get('extraction_notes')): lines.append('- '+stringify(note))
    for item in diff: lines.append('- '+stringify(item))
    lines += ['', '## Module hardware-design edition differences','']
    lines += version_sections or ['- No within-model edition differences reported.']
    lines += ['', '## Citation/page checks','']
    lines += ['- '+p for p in problems] if problems else ['- All normalized source PDF names and 1-based physical page citations resolve within the 13-PDF source manifest.']
    lines += ['', '## Source inventory and method','',f'- Text extracted with Poppler `pdftotext -layout` from all {manifest["total_pages"]} physical pages.', '- Citation page numbering is 1-based PDF page position, not printed page labels.', '- Only supplied PDFs were used to populate technical information; unknowns were not backfilled from memory or outside sources.', '- PDF diagrams and multi-column tables may be imperfect in text extraction; module-level ambiguities preserve locations for manual visual review.']
    (OUT/'validation_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

    records=[]
    for p in sorted(OUT.rglob('*')):
        if p.is_file() and p.name!='output_manifest.json': records.append({'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    dump_json(OUT/'output_manifest.json',{'extraction_date':'2026-10-14','files':records})
    archive=ROOT/'SIM800-datasheet-extraction-2026-10-14.zip'
    if archive.exists(): archive.unlink()
    shutil.make_archive(str(archive)[:-4],'zip',OUT)
    print(json.dumps({'output_dir':str(OUT),'models':len(modules),'at_commands':len(command_rows),'spec_rows':len(spec_rows),'test_rows':len(test_rows),'citations_checked':citation_count,'citation_errors':problems[:100],'citation_error_count':len(problems),'archive':str(archive),'outputs':[str(p) for p in sorted(OUT.rglob('*')) if p.is_file()]},indent=2,ensure_ascii=False))

if __name__=='__main__': main()
