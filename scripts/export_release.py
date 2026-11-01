"""Build a reviewable clean candidate. Never uploads or mutates the live project."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FILES=['cloud_video.py','server.py','runtime_config.py','workflow_transport.py','task_queue.py','storyboard.py','h3_structured.py','source_storyboard.py','coverage_director.py','review_contract.py','trash_manager.py','README.md','AGENTS.md','CHANGELOG.md','DEVELOPMENT.md','THIRD_PARTY_NOTICES.md','Dockerfile','compose.yaml','.env.example','.gitignore','.dockerignore','SECURITY.md','CONTRIBUTING.md']
def export(output):
    output=Path(output).resolve()
    if output==ROOT or output.is_relative_to(ROOT) or ROOT.is_relative_to(output):raise ValueError('输出目录必须位于项目之外，不能覆盖当前项目或上级目录')
    if output.exists() and any(output.iterdir()):raise ValueError('输出目录必须为空，避免覆盖其他文件')
    output.mkdir(parents=True,exist_ok=True)
    selected=[ROOT/f for f in FILES]+([ROOT/'LICENSE'] if (ROOT/'LICENSE').exists() else [])
    for folder in ('static','examples','docs/skills','.github','tests'):
        selected.extend(p for p in (ROOT/folder).rglob('*') if p.is_file())
    selected.extend(ROOT/'docs'/x for x in ('agent-control.md','agent-control.en.md','workflows.md','llms.txt','local-setup.md','local-setup.en.md','operations.md','release-notes.md','source-audit.json','release-validation.json'))
    selected.extend(ROOT/'scripts'/x for x in ('export_release.py','shotdesk_setup.py','shotdesk_smoke.py'))
    for p in set(selected):
        rel=p.relative_to(ROOT)
        if '__pycache__' in rel.parts or '.bak' in p.name or p.is_symlink() or p.name in ('h3-official-SKILL.md','h3-base-en.txt','h3-ref-en.txt'):continue
        target=output/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    # Optional historical Huobao prompt/Skill package stays in the private workspace.
    p=output/'static/index.html';s=p.read_text();s=s.replace('<option value="huobao-native-v1">Huobao 原版（回滚）</option>','');p.write_text(s)
    p=output/'tests/legacy/test_huobao_native.py';s=p.read_text()
    if "optional Huobao package not distributed" not in s:
        s=s.replace('import huobao_native as h',"try:import huobao_native as h\nexcept ImportError:raise unittest.SkipTest('optional Huobao package not distributed')")
        s=s.replace('m=test_queue.m',"m=test_queue.m\nif not (m.ROOT/'docs/huobao-native').exists():raise unittest.SkipTest('optional Huobao package not distributed')")
    p.write_text(s)
    p=output/'tests/legacy/test_storyboard_official.py';s=p.read_text()
    if 'optional unlicensed upstream reference fixtures' not in s:
        s=s.replace('m=test_queue.m',"m=test_queue.m\nif not (m.ROOT/'docs/skills/shotdesk-storyboard/references/h3-ref-en.txt').exists():raise unittest.SkipTest('optional unlicensed upstream reference fixtures are not distributed')")
    p.write_text(s)
    (output/'docs/skills/shotdesk-storyboard/SKILL.md').write_text('---\nname: shotdesk-storyboard\ndescription: Shotdesk structured storyboard adapter\nmetadata:\n  version: h3-structured-v2\n---\nActual current instructions are returned by GET /api/storyboard-skill and implemented by h3_structured.py. Do not inject historical director or Huobao instructions.\n')
    (output/'workflows').mkdir(exist_ok=True);(output/'workflows/.gitkeep').touch()
    bad=[]
    for p in output.rglob('*'):
        if p.is_file() and p.suffix in ('.py','.js','.json','.html','.md','.yaml','.txt'):
            text=p.read_text()
            if re.search('|'.join(('/'+'data/ai','/'+'home/ben',r'192\.168\.3\.214')),text):bad.append(str(p.relative_to(output)))
    if bad:raise ValueError('候选中仍有本机地址，请清理后重建：'+', '.join(bad))
    manifest={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file()}
    (output/'release-manifest.json').write_text(json.dumps({'version':'0.1.0-preview.1','files':manifest,'excluded_upstream_originals':['h3-official-SKILL.md','h3-base-en.txt','h3-ref-en.txt'],'default_storyboard':'h3-structured-v2','license_status':'MIT' if (output/'LICENSE').exists() else 'owner-decision-pending','published':False},ensure_ascii=False,indent=2)+'\n')
    return {'output':str(output),'files':len(manifest),'license_status':'MIT' if (output/'LICENSE').exists() else 'owner-decision-pending'}
def check_ready(root):
    root=Path(root).resolve();manifest=json.loads((root/'release-manifest.json').read_text());blockers=[]
    for name,digest in manifest['files'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:blockers.append('File integrity failed: '+name)
    extra=[str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and str(p.relative_to(root)) not in manifest['files'] and p.name!='release-manifest.json' and '__pycache__' not in p.parts and '.git' not in p.parts and p.suffix!='.pyc']
    if extra:blockers.append('Unexpected files outside the release manifest: '+', '.join(extra[:8]))
    if not (root/'LICENSE').is_file():blockers.append('Owner has not selected an original-code license')
    evidence=root/'docs/release-validation.json'
    try:
        review=json.loads(evidence.read_text())
        if review.get('version')!=manifest.get('version') or not review.get('technical_acceptance_passed'):blockers.append('Technical acceptance has not passed for this version')
    except (OSError,ValueError):blockers.append('Technical acceptance evidence is missing')
    for name in ('h3-official-SKILL.md','h3-base-en.txt','h3-ref-en.txt'):
        if (root/'docs/skills/shotdesk-storyboard/references'/name).exists():blockers.append('Unlicensed upstream original included: '+name)
    return {'version':manifest.get('version'),'ready_for_publication':not blockers,'blockers':blockers,'published':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--output');group.add_argument('--check-ready');args=parser.parse_args()
    result=check_ready(args.check_ready) if args.check_ready else export(args.output)
    print(json.dumps(result,ensure_ascii=False));raise SystemExit(2 if args.check_ready and not result['ready_for_publication'] else 0)
