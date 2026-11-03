import segment_timing
"""h3-structured-v2: the LLM only plans structured JSON clips; code renders the prompt.

The model never types reference labels or asset names into prompt text. It refers to
assets through task-local handles (#A1, #A2 ...), every handle is validated, and the
renderer turns the plan into the official MiniMax H3 Ref2VA six-section English prompt
(docs/skills/shotdesk-storyboard/references/h3-official-SKILL.md, h3-ref-en.txt).
Dialogue stays verbatim in its original language inside <d>[Chinese] ...</d>.
No media generation.
"""
import math
import copy, hashlib, json, re, time

FORMAT = 'h3-structured-v2'
VERSION = 'h3-structured-2026-11-01'
SAMPLING = {'temperature': 0.3, 'top_p': 0.8, 'presence_penalty': 1.0}
MAX_REFS = 4
MAX_CPS = 4.0
MAX_SPEAKERS = 2
ATTEMPTS = 3
MIN_CLIP = 1.0
CHUNK_CHARS = 600
SHOT_SIZES = ['extreme wide shot', 'wide shot', 'full shot', 'medium wide shot', 'medium shot',
              'medium close-up', 'close-up', 'extreme close-up', 'insert shot', 'over-the-shoulder shot', 'two-shot']
CJK = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')
QUOTED = re.compile(r'“[^”]*”|"[^"]*"|「[^」]*」|『[^』]*』|‘[^’]*’|(?<![A-Za-z])\'[^\']*\'(?![A-Za-z])')
CJK_RUN = re.compile(r'[\u3400-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef…]+')
HANDLE = re.compile(r'#(A\d+)(?![\d-])')
GROUP = re.compile(r'^(?:[一二两三四五六七八九十几众多]+人|大家|众人|全体|所有人|众)$')
FIRST_FRAME = 'For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.'
TYPE_EN = {'角色': 'character', '场景': 'scene', '道具': 'prop'}


class StructuredOutputError(ValueError):
    pass


# ---------------------------------------------------------------- model rules
def model_rules(model):
    """Constraints of the target video model. Pika-H3-Flex is a LoRA on the same
    MiniMax H3 Ref2VA node (workflow pika_h3_flex_r2v), so the prompt format is the
    same; only its local workflow accepts integer 5-15 s durations."""
    m = globals().get('CLOUD_MODELS',{}).get(str(model),str(model or ''))
    if 'seedance' in m.lower():
        return {'family':'seedance','min':4,'max':30 if '2.5' in m or '2-5' in m else 15,'integer':True,'h3':False}
    if 'pika' in m.lower():
        return {'family': 'pika-h3-flex', 'min': 5, 'max': 15, 'integer': True, 'h3': True}
    if re.search(r'minimax|(?:^|[-_])h3(?:[-_]|$)', m, re.I):
        return {'family': 'minimax-h3', 'min': 4, 'max': 15, 'integer': str(model).startswith('cloud-'), 'h3': True}
    return {'family': 'generic', 'min': 4, 'max': 15, 'integer': False, 'h3': False}


def spoken_len(text):
    return len(re.findall(r'\w', str(text or '')))


def norm(text):
    return re.sub(r'\s+', '', str(text or ''))


def ts(seconds):
    seconds = max(0.0, float(seconds))
    return f'{int(seconds // 60):02d}:{seconds % 60:06.3f}'


def english_only(text):
    return not CJK.search(QUOTED.sub('', str(text or '')))


def fix_cjk(obj, cat):
    """Mechanical: in English fields, an unquoted Chinese run that is exactly an asset name becomes
    its #handle; any other unquoted Chinese run is visible text and gets quotes. Wording is unchanged."""
    names = {r['name']: r['handle'] for r in cat}

    def fix(text):
        if not isinstance(text, str) or english_only(text):
            return text
        out, last = [], 0
        for m in QUOTED.finditer(text):
            out.append(('raw', text[last:m.start()])); out.append(('q', m[0])); last = m.end()
        out.append(('raw', text[last:]))
        def one(m):
            run = m[0]
            if not CJK.search(run):
                return run
            return '#' + names[run] if run in names else '“' + run + '”'
        return ''.join(CJK_RUN.sub(one, t) if kind == 'raw' else t for kind, t in out)
    for row in obj.get('shots') or [] if isinstance(obj, dict) else []:
        if not isinstance(row, dict):
            continue
        for k in ('summary_en', 'look_en', 'soundscape_en', 'music_en'):
            if k in row:
                row[k] = fix(row[k])
        for c in row.get('clips') or []:
            if isinstance(c, dict):
                for k in ('camera', 'action', 'delivery'):
                    if k in c:
                        c[k] = fix(c[k])
    return obj


# ---------------------------------------------------------------- catalog / script
def catalog(p):
    rows = []
    n = 0
    for a in p.get('assets', []):
        if a.get('type') not in ('角色', '场景', '道具'):
            continue
        n += 1
        h = 'A' + str(n)
        looks = []
        if a['type'] == '角色':
            for i, l in enumerate(a.get('looks', [])):
                looks.append({'handle': h + '-' + str(i + 1), 'id': l['id'], 'name': l.get('name', ''),
                              'description': str(l.get('prompt', ''))[:400], 'has_image': bool(l.get('image'))})
        rows.append({'handle': h, 'id': a['id'], 'type': a['type'], 'name': a.get('name', ''),
                     'description': str(a.get('prompt') or a.get('description') or '')[:400],
                     'default_look': next((l['handle'] for l in looks if l['id'] == a.get('default_look_id')), None),
                     'looks': looks, 'has_image': bool(a.get('image') or any(l['has_image'] for l in looks))})
    return rows


def dialogue_lines(text, cat):
    names = {r['name']: r['handle'] for r in cat if r['type'] == '角色'}
    out = []
    for raw in str(text or '').split('\n'):
        line = raw.strip()
        m = re.match(r'^([^：:\s【（(]{1,12})[：:]\s*(.+)$', line)
        if not m:
            continue
        label, words = m[1], m[2].strip()
        parts = [x for x in re.split(r'[、，,和与及]', label) if x]
        if label in names:
            speakers = [names[label]]
        elif len(parts) > 1 and all(x in names for x in parts):
            speakers = [names[x] for x in parts]
        elif GROUP.match(label):
            speakers = None
        else:
            continue
        if spoken_len(words):
            out.append({'label': label, 'speakers': speakers, 'text': words})
    return out


def chunks(script, limit=CHUNK_CHARS):
    """Split by '场景 N' headings, then by blank-line paragraphs; never across a scene."""
    scenes = [s for s in re.split(r'(?m)^(?=场景\s*\d+\s*$)', str(script or '')) if s.strip()]
    out = []
    for scene in scenes:
        heading = scene.strip().split('\n', 1)[0].strip()
        meta = ' '.join(x.strip() for x in scene.strip().split('\n')[:8] if x.strip())[:160]
        cur = ''
        for para in re.split(r'\n\s*\n', scene):
            if not para.strip():
                continue
            if cur and len(cur) + len(para) > limit:
                out.append({'heading': heading, 'scene_meta': meta, 'text': cur.strip()})
                cur = ''
            cur += para.strip() + '\n\n'
        if cur.strip():
            out.append({'heading': heading, 'scene_meta': meta, 'text': cur.strip()})
    return out


MAX_LINE_PIECE = 40


def number_lines(lines):
    """Give each script line (long ones split at sentence ends) a task-local id L1..Ln.
    The LLM only places ids; code inserts the verbatim text and the speakers."""
    out = []
    for x in lines:
        pieces, cur = [], ''
        for part in re.findall(r'[^。！？!?…]+[。！？!?…”」』"]*|[。！？!?…]+', x['text']):
            if cur and spoken_len(cur + part) > MAX_LINE_PIECE:
                pieces.append(cur); cur = ''
            cur += part
        if cur.strip():
            pieces.append(cur)
        for piece in pieces or [x['text']]:
            out.append(dict(x, id='L' + str(len(out) + 1), text=piece.strip()))
    return out


def llm_lines(numbered, cat):
    names = {r['handle']: r['name'] for r in cat}
    return [{'id': x['id'], 'speaker': x['label'] + ('（' + '、'.join('#' + h for h in x['speakers']) + '）' if x['speakers'] else '（群声：由该 clip 入画的角色齐声说）'),
             'text': x['text'], 'chars': spoken_len(x['text']), 'min_seconds': math.ceil(spoken_len(x['text']) / MAX_CPS)} for x in numbered]


def line_sort_key(lid):
    m = re.match(r'^L(\d+)$', str(lid))
    return (0, int(m[1])) if m else (1, str(lid))


def reorder_line_ids(obj, numbered):
    """If clips cover exactly the expected line_ids as a set (no miss/dup) but in the wrong order,
    redistribute L1..Ln into those clips in script order, keeping each clip's line count and staging."""
    order = [x['id'] for x in numbered]
    spoken = []
    for row in obj.get('shots') or [] if isinstance(obj, dict) else []:
        if not isinstance(row, dict):
            continue
        for c in row.get('clips') or []:
            if isinstance(c, dict) and c.get('line_ids'):
                c['line_ids'] = sorted(c['line_ids'], key=line_sort_key)
                spoken.append(c)
    flat = [x for c in spoken for x in c['line_ids']]
    if len(flat) != len(order) or sorted(flat, key=line_sort_key) != sorted(order, key=line_sort_key):
        return False
    if flat == order:
        return True
    i = 0
    for c in spoken:
        n = len(c['line_ids'])
        c['line_ids'] = order[i:i + n]
        i += n
    return True


def resolve_lines(obj, numbered, cat):
    """Turn clip.line_ids into line/speaker_ids (verbatim text and speakers come from the script).
    A clip whose ids belong to different speakers is split mechanically into consecutive sub-clips.
    Wrong L-order with the same id set is reordered in place (not an error). Hard-fail only on
    missing/duplicate ids, bad ids, or group-speaker issues."""
    reorder_line_ids(obj, numbered)
    by_id = {x['id']: x for x in numbered}
    chars = {r['handle'] for r in cat if r['type'] == '角色'}
    errors, seen = [], []
    for i, row in enumerate(obj.get('shots') or [] if isinstance(obj, dict) else [], 1):
        if not isinstance(row, dict) or not isinstance(row.get('clips'), list):
            continue
        tag = f'shot{i}（{str(row.get("title", ""))[:12]}）'
        cast = [c.get('asset') for c in row.get('cast') or [] if isinstance(c, dict)]
        out = []
        for j, c in enumerate(row['clips'], 1):
            if not isinstance(c, dict):
                out.append(c); continue
            ids = list(c.get('line_ids') or [])
            c['line'], c['speaker_ids'] = None, []
            if not ids:
                c['delivery'] = None
                out.append(c); continue
            bad = [x for x in ids if x not in by_id]
            if bad:
                errors.append(f'{tag}clip{j} line_ids 含不存在的编号 ' + '、'.join(map(str, bad)))
                out.append(c); continue
            seen.extend(ids)
            groups = []
            for x in ids:
                sp = by_id[x]['speakers']
                if sp is None:
                    sp = [h for h in c.get('subject_ids') or [] if h in chars and h in cast]
                    if len(sp) < 2:
                        errors.append(f'{tag}clip{j} {x} 是群声台词，subject_ids 须包含至少 2 个齐声说话的角色')
                if groups and sorted(groups[-1][0]) == sorted(sp):
                    groups[-1][1].append(x)
                else:
                    groups.append((list(sp), [x]))
            st, en = c.get('start'), c.get('end')
            if len(groups) > 1 and isinstance(st, (int, float)) and isinstance(en, (int, float)):
                needs = [max(MIN_CLIP, spoken_len(''.join(by_id[x]['text'] for x in g[1])) / MAX_CPS) for g in groups]
                total = sum(needs)
                # Prefer keeping the original span when it is long enough; otherwise extend (caller stretches the shot).
                span = max(en - st, total)
                t = float(st)
                for k, (sp, gids) in enumerate(groups):
                    end = round(float(st) + span, 2) if k == len(groups) - 1 else round(t + needs[k] * span / total, 2)
                    if end - t < needs[k] - 1e-6:
                        end = round(t + needs[k], 2)
                    sub = dict(c, start=t, end=end, new_cut=c.get('new_cut') if k == 0 else False,
                               line=''.join(by_id[x]['text'] for x in gids), speaker_ids=list(sp), _verbatim=True)
                    out.append(sub); t = end
                continue
            c['line'] = ''.join(by_id[x]['text'] for x in ids)
            c['speaker_ids'] = list(groups[-1][0])
            c['_verbatim'] = True
            out.append(c)
        row['clips'] = out
    order = [x['id'] for x in numbered]
    missing = [x for x in order if x not in seen]
    dup = sorted({x for x in seen if seen.count(x) > 1}, key=order.index)
    if missing:
        errors.append('遗漏台词编号（每个都必须放进某个 clip 的 line_ids）：' + '、'.join(missing[:20]))
    if dup:
        errors.append('台词编号重复使用：' + '、'.join(dup[:20]))
    # Order: already fixed by reorder_line_ids when the set matches; do not hard-fail on order alone.
    if not missing and not dup and seen != order:
        # Should be rare (e.g. reorder ran before split changed ids); try once more after resolve build.
        pass
    return errors


def drop_unused_props(obj):
    """Mechanical: a prop that no clip shows or mentions does not need a reference image."""
    for row in obj.get('shots') or [] if isinstance(obj, dict) else []:
        if not isinstance(row, dict) or not isinstance(row.get('props'), list):
            continue
        text = json.dumps([row.get('clips'), row.get('summary_en'), row.get('look_en')], ensure_ascii=False)
        used = {h for c in row.get('clips') or [] if isinstance(c, dict) for h in c.get('subject_ids') or []}
        row['props'] = [h for h in row['props'] if h in used or re.search('#' + re.escape(str(h)) + r'(?![\d-])', text)]
    return obj


def trim_refs(obj, cat):
    """If refs exceed MAX_REFS, drop props first, then non-speaking cast (least used). Strip orphan #handles."""
    chars = {r['handle'] for r in cat if r['type'] == '角色'}
    for row in obj.get('shots') or [] if isinstance(obj, dict) else []:
        if not isinstance(row, dict):
            continue
        cast = [c for c in row.get('cast') or [] if isinstance(c, dict)]
        props = list(row.get('props') or [])
        scene = row.get('scene')
        clips = [c for c in row.get('clips') or [] if isinstance(c, dict)]
        speakers = {h for c in clips for h in c.get('speaker_ids') or []}
        def refs():
            return list(dict.fromkeys(([scene] if scene else []) + [c.get('asset') for c in cast] + props))
        while len(refs()) > MAX_REFS and props:
            drop = props.pop()
            for c in clips:
                c['subject_ids'] = [h for h in c.get('subject_ids') or [] if h != drop]
        while len(refs()) > MAX_REFS:
            cast_ids = [c.get('asset') for c in cast]
            candidates = [h for h in cast_ids if h not in speakers]
            if not candidates:
                break
            usage = {h: sum(1 for c in clips if h in (c.get('subject_ids') or [])) for h in candidates}
            drop = min(candidates, key=lambda h: (usage.get(h, 0), cast_ids.index(h)))
            cast = [c for c in cast if c.get('asset') != drop]
            for c in clips:
                c['subject_ids'] = [h for h in c.get('subject_ids') or [] if h != drop]
        used = {h for c in clips for h in (c.get('subject_ids') or []) + (c.get('speaker_ids') or [])}
        cast = [c for c in cast if c.get('asset') in used or c.get('asset') in speakers]
        row['cast'], row['props'] = cast, props
        keep = set(refs())
        def strip(text):
            if not isinstance(text, str):
                return text
            return HANDLE.sub(lambda m: m[0] if m[1] in keep else 'someone', text)
        for k in ('summary_en', 'look_en', 'soundscape_en', 'music_en'):
            if k in row:
                row[k] = strip(row[k])
        for c in clips:
            for k in ('camera', 'action', 'delivery'):
                if k in c:
                    c[k] = strip(c[k])
    return obj


def stretch_for_cps(obj, rules):
    """Restitch clip timeline and extend spoken clips so each is ≤ MAX_CPS (duration capped at model max)."""
    for row in obj.get('shots') or [] if isinstance(obj, dict) else []:
        if not isinstance(row, dict) or not isinstance(row.get('clips'), list) or not row['clips']:
            continue
        clips = [c for c in row['clips'] if isinstance(c, dict)]
        t = 0.0
        for c in clips:
            need = max(MIN_CLIP, spoken_len(c['line']) / MAX_CPS) if c.get('line') else MIN_CLIP
            span = max(need, float(c.get('end', 0)) - float(c.get('start', 0)), MIN_CLIP)
            c['start'] = round(t, 2)
            c['end'] = round(t + span, 2)
            t = c['end']
        d = t
        if rules.get('integer'):
            d = float(math.ceil(d - 1e-9))
            clips[-1]['end'] = d
        row['duration'] = min(float(rules['max']), max(float(rules['min']), d))
        clips[-1]['end'] = float(row['duration'])
        row['clips'] = clips
    return obj


def split_overfull_speakers(obj, rules):
    """If a shot has > MAX_SPEAKERS voice events, split it into consecutive shots of ≤ MAX_SPEAKERS each."""
    rows = obj.get('shots') if isinstance(obj, dict) else None
    if not isinstance(rows, list):
        return obj
    out = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('clips'), list):
            out.append(row); continue
        packs, cur, voices = [], [], set()
        for c in row['clips']:
            v = tuple(sorted(c.get('speaker_ids') or [])) if c.get('line') else None
            if v is not None and v not in voices and len(voices) >= MAX_SPEAKERS and cur:
                packs.append(cur); cur, voices = [], set()
            cur.append(c)
            if v is not None:
                voices.add(v)
        if cur:
            packs.append(cur)
        if len(packs) <= 1:
            out.append(row); continue
        for n, pack in enumerate(packs):
            t0 = float(pack[0]['start'])
            local = []
            for c in pack:
                nc = dict(c, start=round(float(c['start']) - t0, 2), end=round(float(c['end']) - t0, 2))
                if local:
                    nc['new_cut'] = bool(c.get('new_cut'))
                else:
                    nc['new_cut'] = True
                local.append(nc)
            if local and abs(local[0]['start']) > 1e-6:
                shift = local[0]['start']
                for c in local:
                    c['start'] = round(c['start'] - shift, 2); c['end'] = round(c['end'] - shift, 2)
            dur = float(local[-1]['end'])
            if rules.get('integer'):
                dur = float(max(rules['min'], math.ceil(dur - 1e-9)))
                local[-1]['end'] = dur
            dur = min(float(rules['max']), max(float(rules['min']), dur))
            local[-1]['end'] = dur
            used = {h for c in local for h in (c.get('subject_ids') or []) + (c.get('speaker_ids') or [])}
            cast = [c for c in row.get('cast') or [] if isinstance(c, dict) and c.get('asset') in used]
            props = [h for h in row.get('props') or [] if h in used]
            title = row.get('title') or ''
            if n:
                title = f'{title}-{n + 1}'[:30]
            out.append(dict(row, title=title, clips=local, duration=dur, cast=cast, props=props,
                            description_zh=(row.get('description_zh') or '') + f'（分段{n + 1}）'))
    obj['shots'] = out
    return obj


# ---------------------------------------------------------------- LLM schema & instruction
INSTRUCTION = """你是短剧分镜导演。把给定剧本片段拆成可直接用于 H3 参考生视频（Ref2VA）的视频片段：每个 shot = 一次独立的视频生成。只输出符合 schema 的 JSON，平台会把它编译成 H3 官方英文提示词。

硬规则（程序逐条校验，不合格会把错误退回让你重写）：
1. 时长：每个 shot 时长须在 {min}-{max} 秒{integer}。clips 从 0 开始首尾相接，最后一个 end 等于 shot 时长，每个 clip 至少 1 秒。new_cut=true 表示切到新机位/景别；false 表示同一机位里的连续动作。
2. 参考图：scene + cast（出镜或说话的角色）+ props 合计最多 4 个。优先保留场景和说话/出镜角色；非关键道具不放；人多时拆成多个 shot，或让次要角色不入画。
3. 造型：cast 中每个角色必须从该角色自己的 looks 里选 look（按剧情时间与服装判断，例如“次日入职”后要换成对应造型，戴上面罩时用对应造型）。
4. 台词：不要抄写台词。dialogue_in_chunk 里每句台词有编号（L1、L2…），在 clip 的 line_ids 里填编号即可，程序会填入原句和说话人。每个编号必须且只能用一次；clip 序列中的编号应尽量按 L1→L2→L3… 出现（若集合正确但顺序乱了，程序会自动重排）。示例：dialogue 有 L1/L2/L3 时，第一个说话 clip 用 ["L1"]，下一个用 ["L2"]，再下一个用 ["L3"]，不要先写 L3 再写 L1。最好一个 clip 只放同一说话方的台词（若放了多人的台词，程序会按字数拆成连续子 clip）。群声台词所在 clip 的 subject_ids 要包含齐声说话的角色。没有台词的 clip：line_ids 填 []，delivery 填 null。delivery 写英文语气短语（如 "calmly, without looking up"）。
5. 语速：clip 时长 ≥ 该 clip 所有台词 min_seconds 之和（4 字/秒）；每个 shot 最多 2 个说话方（齐声算 1 个）——第 3 个人开口就切到下一个 shot。放不下就加长 clip、拆 clip 或拆 shot。
6. 说话的角色必须在本 shot 的 cast 中；subject_ids 只能用本 shot 的 scene/cast/props；cast 里的每个角色都必须在某个 clip 的 subject_ids 中出现或说话。
7. 英文字段（camera、action、delivery、summary_en、look_en、soundscape_en、music_en）只写英文；用 #A编号 指代角色/场景/道具（例如 "#A4 slams the travel bag onto the counter"），绝不写中文名；画面中可见的文字可以用引号保留原文（例如 the screen shows "正在加载……99%"）。action 写具体可见的动作、表情、站位，不写心理活动、抽象情绪或剧情总结；只能提到本 shot 引用的编号。
8. title、description_zh、image_prompt_zh 用中文写给人看；image_prompt_zh 是第一个 clip 的静态构图。
9. 不要写 <Subject>、<Picture>、@ 符号或图片编号；这些由程序生成。music_en 没有配乐就写 N/A。
"""


def instruction(rules):
    return INSTRUCTION.replace('{min}', str(rules['min'])).replace('{max}', str(rules['max'])).replace(
        '{integer}', '，且必须是整数秒' if rules['integer'] else '')


def schema(cat, rules, max_shots=12, line_ids=()):
    chars = [r for r in cat if r['type'] == '角色']
    scenes = [r['handle'] for r in cat if r['type'] == '场景']
    props = [r['handle'] for r in cat if r['type'] == '道具']
    handles = [r['handle'] for r in cat]
    cast_choices = [{'type': 'object', 'properties': {'asset': {'const': c['handle']},
                                                        'look': {'enum': [l['handle'] for l in c['looks']] or [None]}},
                     'required': ['asset', 'look'], 'additionalProperties': False} for c in chars]
    num = {'type': 'number', 'minimum': 0, 'maximum': rules['max']}
    duration = {'type': 'integer' if rules['integer'] else 'number', 'minimum': rules['min'], 'maximum': rules['max']}
    s = lambda n: {'type': 'string', 'maxLength': n}
    clip = {'type': 'object', 'properties': {
        'start': num, 'end': num, 'new_cut': {'type': 'boolean'}, 'shot_size': {'enum': SHOT_SIZES},
        'camera': s(120), 'subject_ids': {'type': 'array', 'items': {'enum': handles}, 'maxItems': MAX_REFS},
        'action': s(450),
        'line_ids': {'type': 'array', 'items': {'enum': list(line_ids)}, 'maxItems': 3} if line_ids else {'type': 'array', 'maxItems': 0},
        'delivery': {'anyOf': [{'type': 'null'}, s(80)]}},
        'required': ['start', 'end', 'new_cut', 'shot_size', 'camera', 'subject_ids', 'action', 'line_ids', 'delivery'],
        'additionalProperties': False}
    shot = {'type': 'object', 'properties': {
        'title': s(30), 'description_zh': s(400), 'image_prompt_zh': s(200), 'duration': duration,
        'scene': {'enum': scenes + [None]},
        'cast': {'type': 'array', 'items': {'anyOf': cast_choices} if cast_choices else {'type': 'null'}, 'maxItems': MAX_REFS if cast_choices else 0},
        'props': {'type': 'array', 'items': {'enum': props or ['A0']}, 'maxItems': MAX_REFS},
        'summary_en': s(400), 'look_en': s(200), 'clips': {'type': 'array', 'minItems': 1, 'maxItems': 6, 'items': clip},
        'soundscape_en': s(300), 'music_en': s(200)},
        'required': ['title', 'description_zh', 'image_prompt_zh', 'duration', 'scene', 'cast', 'props', 'summary_en',
                     'look_en', 'clips', 'soundscape_en', 'music_en'], 'additionalProperties': False}
    return {'type': 'object', 'properties': {'shots': {'type': 'array', 'minItems': 1, 'maxItems': max_shots, 'items': shot}},
            'required': ['shots'], 'additionalProperties': False}


def llm_catalog(cat):
    out = []
    for r in cat:
        row = {'id': r['handle'], 'type': r['type'], 'name': r['name'], 'description': r['description'][:200]}
        if r['type'] == '角色':
            row['looks'] = [{'id': l['handle'], 'name': l['name'], 'description': l['description'][:200]} for l in r['looks']]
            row['default_look'] = r['default_look']
        out.append(row)
    return out


# ---------------------------------------------------------------- validation (LLM handle space)
def autofix(obj, rules):
    """Only mechanical snapping (float noise); never content changes."""
    for row in obj.get('shots', []) if isinstance(obj, dict) else []:
        clips = row.get('clips') if isinstance(row, dict) else None
        if not isinstance(clips, list) or not clips:
            continue
        for c in clips:
            for k in ('start', 'end'):
                if isinstance(c.get(k), (int, float)):
                    c[k] = round(float(c[k]), 2)
        if isinstance(clips[0], dict):
            clips[0]['new_cut'] = True
            if isinstance(clips[0].get('start'), float) and abs(clips[0]['start']) <= 0.3:
                clips[0]['start'] = 0.0
        d = row.get('duration')
        last = clips[-1]
        if isinstance(d, (int, float)) and isinstance(last.get('end'), (int, float)) and abs(last['end'] - d) <= 0.3:
            last['end'] = float(d)
        for a, b in zip(clips, clips[1:]):
            if isinstance(a.get('end'), (int, float)) and isinstance(b.get('start'), (int, float)) and abs(a['end'] - b['start']) <= 0.3:
                b['start'] = a['end']
    return obj


def line_matches(line, speakers, script_lines, cat_names):
    """Return '' if the line is a verbatim fragment of a script line by those speakers."""
    n = norm(line)
    candidates = [x for x in script_lines if n and n in norm(x['text'])]
    if not candidates:
        return '台词“' + str(line)[:40] + '”不是剧本原句的逐字片段'
    for x in candidates:
        if x['speakers'] is None:
            if len(speakers) >= 2:
                return ''
        elif sorted(x['speakers']) == sorted(speakers):
            return ''
    who = '/'.join(x['label'] for x in candidates)
    return '台词“' + str(line)[:30] + '”在剧本中由 ' + who + ' 说，speaker_ids 填写为 ' + '、'.join(cat_names.get(s, s) for s in speakers)


def validate_rows(obj, cat, rules, chunk_lines, script_lines, coverage=True):
    by = {r['handle']: r for r in cat}
    names = {r['handle']: r['name'] for r in cat}
    errors = []
    rows = obj.get('shots') if isinstance(obj, dict) else None
    if not isinstance(rows, list) or not rows:
        return ['shots 必须是非空列表']
    spoken = []
    for i, row in enumerate(rows, 1):
        tag = f'shot{i}（{str(row.get("title", ""))[:12]}）'
        if not isinstance(row, dict):
            errors.append(tag + '不是对象'); continue
        d = row.get('duration')
        if isinstance(d, bool) or not isinstance(d, (int, float)) or not rules['min'] <= d <= rules['max']:
            errors.append(f'{tag}时长 {d} 不在 {rules["min"]}-{rules["max"]} 秒'); continue
        if rules['integer'] and float(d) != int(d):
            errors.append(f'{tag}时长须为整数秒（{rules["family"]}）')
        scene = row.get('scene')
        cast = row.get('cast') or []
        props = row.get('props') or []
        if scene is not None and (scene not in by or by[scene]['type'] != '场景'):
            errors.append(f'{tag}scene {scene} 不是场景编号')
        cast_ids = []
        for c in cast:
            h = c.get('asset') if isinstance(c, dict) else None
            if h not in by or by[h]['type'] != '角色':
                errors.append(f'{tag}cast 中 {h} 不是角色编号'); continue
            look = c.get('look')
            looks = [l['handle'] for l in by[h]['looks']]
            if looks and look not in looks:
                errors.append(f'{tag}{names[h]} 的造型 {look} 不属于该角色，可选：' + '、'.join(l['handle'] + '=' + l['name'] for l in by[h]['looks']))
            if h in cast_ids:
                errors.append(f'{tag}cast 中 {names[h]} 重复')
            cast_ids.append(h)
        for h in props:
            if h not in by or by[h]['type'] != '道具':
                errors.append(f'{tag}props 中 {h} 不是道具编号')
        refs = list(dict.fromkeys(([scene] if scene else []) + cast_ids + list(props)))
        if len(refs) > MAX_REFS:
            errors.append(f'{tag}参考图 {len(refs)} 张（场景+角色+道具）超过 {MAX_REFS} 张：去掉非关键道具，或拆镜/让次要角色不入画')
        clips = row.get('clips') or []
        if not clips:
            errors.append(tag + '缺少 clips'); continue
        prev_end = 0.0
        used = set()
        voice_events = []
        for j, c in enumerate(clips, 1):
            ct = f'{tag}clip{j}'
            st, en = c.get('start'), c.get('end')
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (st, en)):
                errors.append(ct + ' start/end 须为数字'); continue
            if abs(st - prev_end) > 0.05:
                errors.append(f'{ct}开始于 {st}s，应紧接上一段 {prev_end:g}s')
            if en - st < MIN_CLIP - 1e-6:
                errors.append(f'{ct}长 {en - st:.2f}s，至少 {MIN_CLIP:g}s')
            prev_end = en
            subj = c.get('subject_ids') or []
            for h in subj:
                if h not in refs:
                    errors.append(f'{ct}subject_ids 中 {h} 不在本 shot 的 scene/cast/props')
            used.update(subj)
            spk = list(c.get('speaker_ids') or [])
            line = c.get('line')
            if spk and not (isinstance(line, str) and line.strip()):
                errors.append(ct + '有 speaker_ids 但没有 line')
            if isinstance(line, str) and line.strip():
                if not spk:
                    errors.append(ct + '有台词但 speaker_ids 为空')
                for h in spk:
                    if h not in cast_ids:
                        errors.append(f'{ct}说话人 {names.get(h, h)} 不在本 shot 的 cast 中')
                msg = '' if c.get('_verbatim') else line_matches(line, spk, script_lines, names)
                if msg:
                    errors.append(ct + msg)
                length = en - st
                if length > 0 and spoken_len(line) / length > MAX_CPS + 1e-6:
                    errors.append(f'{ct}台词 {spoken_len(line)} 字放在 {length:.1f}s 里（{spoken_len(line) / length:.1f} 字/秒 > {MAX_CPS:g}）：加长该 clip，或把台词按原顺序拆到下一 clip/下一 shot')
                voice_events.append(tuple(sorted(spk)))
                spoken.append(line)
                used.update(spk)
            for k in ('camera', 'action', 'delivery'):
                v = c.get(k)
                if isinstance(v, str) and not english_only(v):
                    errors.append(f'{ct}.{k} 须为英文并用 #A编号指代，不写中文名：' + v[:80])
                for h in HANDLE.findall(v or ''):
                    if h not in by:
                        errors.append(f'{ct}.{k} 引用了不存在的编号 #{h}')
                    elif k == 'action' and h not in refs:
                        errors.append(f'{ct}.action 提到 #{h}（{names[h]}），但它不在本 shot 的参考图中：加入 cast/props 或不要让其入画')
        if clips and isinstance(clips[-1].get('end'), (int, float)) and isinstance(d, (int, float)) and abs(clips[-1]['end'] - d) > 0.05:
            errors.append(f'{tag}最后一个 clip 结束于 {clips[-1]["end"]}s，须等于时长 {d}s')
        if len(set(voice_events)) > MAX_SPEAKERS:
            errors.append(f'{tag}有 {len(set(voice_events))} 个说话方，超过 {MAX_SPEAKERS}：拆成多个 shot')
        for h in cast_ids:
            if h not in used:
                errors.append(f'{tag}cast 中 {names[h]} 没有在任何 clip 出镜或说话，请删除或安排入画')
        for k in ('summary_en', 'look_en', 'soundscape_en', 'music_en'):
            v = row.get(k)
            if not isinstance(v, str) or not v.strip():
                errors.append(f'{tag}.{k} 不能为空'); continue
            if not english_only(v):
                errors.append(f'{tag}.{k} 须为英文，用 #A编号指代')
            for h in HANDLE.findall(v):
                if h not in refs:
                    errors.append(f'{tag}.{k} 提到 #{h}，但它不在本 shot 的参考图中')
        for k in ('title', 'description_zh', 'image_prompt_zh'):
            if not isinstance(row.get(k), str) or not row[k].strip():
                errors.append(f'{tag}.{k} 不能为空')
    if coverage and chunk_lines:
        joined = norm(''.join(spoken))
        missing = [x for x in chunk_lines if norm(x['text']) not in joined]
        if missing:
            errors.append('遗漏剧本台词（每句都要出现）：' + '；'.join(x['label'] + '：' + x['text'][:30] for x in missing[:8]))
    return errors


# ---------------------------------------------------------------- profiles (English subject descriptions)
def profile_key(asset_id, look_id=None):
    return asset_id + (':' + look_id if look_id else '')


def asset_profiles(api, task, cat):
    keys = {}
    for r in cat:
        if r['type'] == '角色' and r['looks']:
            for l in r['looks']:
                keys[l['handle']] = {'asset': r['name'], 'type': 'character', 'look': l['name'],
                                     'description': (r['description'] + '；' + l['description'])[:500]}
        else:
            keys[r['handle']] = {'asset': r['name'], 'type': TYPE_EN[r['type']], 'description': r['description'][:500]}
    item = {'type': 'object', 'properties': {'en': {'type': 'string', 'maxLength': 260}, 'short': {'type': 'string', 'maxLength': 50},
                                            'voice': {'type': 'string', 'maxLength': 90}},
            'required': ['en', 'short', 'voice'], 'additionalProperties': False}
    sch = {'type': 'object', 'properties': {'profiles': {'type': 'object', 'properties': {k: item for k in keys},
                                                         'required': list(keys), 'additionalProperties': False}},
           'required': ['profiles'], 'additionalProperties': False}
    system = ('Write concise English visual profiles for video-generation reference subjects. For each key: '
              '"en" = one noun phrase (max 30 words) describing only visible, stable appearance (age range, gender, build, hair, clothing/outfit, '
              'key accessories; for scenes: layout, materials, lighting; for props: shape, color, material). No names, no story, no Chinese. '
              '"short" = 2-5 word noun phrase starting with "the" (e.g. "the masked robber"). '
              '"voice" = for characters a short voice description (e.g. "a gruff young male voice"), otherwise empty string. Output JSON only.')
    messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps(keys, ensure_ascii=False)}]
    last = 'no output'
    for attempt in range(ATTEMPTS):
        resp = api.Q.text_request({'model': task['model'], 'messages': messages, 'temperature': 0.2, 'top_p': 0.8,
                                   'max_tokens': 6000, 'response_format': {'type': 'json_schema', 'json_schema': {'name': 'h3_profiles', 'schema': sch}},
                                   'chat_template_kwargs': {'enable_thinking': False}}, task)
        raw = re.sub(r'<think>.*?</think>', '', resp['choices'][0]['message'].get('content') or '', flags=re.S)
        try:
            obj = json.loads(raw[raw.find('{'):raw.rfind('}') + 1])['profiles']
            bad = [k for k in keys if not isinstance(obj.get(k), dict) or not english_only(obj[k].get('en', '') + obj[k].get('short', '') + obj[k].get('voice', '')) or not obj[k].get('en', '').strip()]
            if bad:
                raise ValueError('these keys must be non-empty English only: ' + ', '.join(bad))
        except (ValueError, KeyError, TypeError) as exc:
            last = str(exc)
            messages = messages[:2] + [{'role': 'assistant', 'content': raw[:8000]}, {'role': 'user', 'content': 'Fix: ' + last + '. Return the complete JSON.'}]
            continue
        out = {}
        for r in cat:
            if r['type'] == '角色' and r['looks']:
                for l in r['looks']:
                    out[profile_key(r['id'], l['id'])] = obj[l['handle']]
                out[r['id']] = obj[r['looks'][0]['handle']]
            else:
                out[r['id']] = obj[r['handle']]
        return out
    raise StructuredOutputError('英文主体描述生成失败：' + last)


# ---------------------------------------------------------------- planning
def to_plan(row, cat, profiles):
    by = {r['handle']: r for r in cat}
    looks = {l['handle']: l['id'] for r in cat for l in r['looks']}
    cast = [{'asset_id': by[c['asset']]['id'], 'look_id': looks.get(c.get('look'))} for c in row.get('cast') or []]
    refs = ([by[row['scene']]['id']] if row.get('scene') else []) + [c['asset_id'] for c in cast] + [by[h]['id'] for h in row.get('props') or []]
    refs = list(dict.fromkeys(refs))
    used_profiles = {}
    for c in cast:
        k = profile_key(c['asset_id'], c['look_id'])
        used_profiles[k] = profiles.get(k) or profiles.get(c['asset_id'])
    for aid in refs:
        if aid not in [c['asset_id'] for c in cast]:
            used_profiles[aid] = profiles.get(aid)
    clips = []
    for c in row['clips']:
        clips.append({'start': float(c['start']), 'end': float(c['end']), 'new_cut': bool(c.get('new_cut')),
                      'shot_size': c['shot_size'], 'camera': c.get('camera') or '', 'action': c.get('action') or '',
                      'subjects': [by[h]['id'] for h in c.get('subject_ids') or []],
                      'speakers': [by[h]['id'] for h in c.get('speaker_ids') or []],
                      'line': c.get('line') if isinstance(c.get('line'), str) and c['line'].strip() else None,
                      'delivery': c.get('delivery') if isinstance(c.get('delivery'), str) and c['delivery'].strip() else None})
    return {'version': VERSION, 'duration': row['duration'], 'scene': by[row['scene']]['id'] if row.get('scene') else None,
            'cast': cast, 'props': [by[h]['id'] for h in row.get('props') or []], 'refs': refs, 'clips': clips,
            'summary_en': row['summary_en'], 'look_en': row['look_en'], 'soundscape_en': row['soundscape_en'],
            'music_en': row['music_en'], 'handles': {r['handle']: r['id'] for r in cat}, 'profiles': used_profiles}


def build_shot(api, p, plan, row, mode, model):
    names = {a['id']: a.get('name', '') for a in p['assets']}
    text = render(p, plan, mode, model)
    dialogue = [{'speaker': '、'.join(names.get(s, s) for s in c['speakers']), 'text': c['line']} for c in plan['clips'] if c['line']]
    return {'id': api.uid(), 'title': row['title'], 'description': row['description_zh'], 'image_prompt': row['image_prompt_zh'],
            'duration': plan['duration'], 'asset_ids': list(plan['refs']),
            'character_looks': {c['asset_id']: c['look_id'] for c in plan['cast'] if c['look_id']},
            'dialogue': dialogue, 'video_prompt': text, 'h3_rendered': text, 'h3_plan': plan,
            'prompt_format': FORMAT, 'storyboard_scheme': FORMAT, 'prompt_video_model': model, 'prompt_video_mode': mode,
            'versions': [], 'video_override': None}


def ask_rows(api, task, cat, rules, payload, chunk_lines, script_lines, coverage=True, max_shots=12, label=''):
    sch = schema(cat, rules, max_shots, [x['id'] for x in chunk_lines])
    task_instruction=instruction(rules)
    if payload.get('storyboard_requirements'):
        task_instruction+='\n用户的分镜补充要求见storyboard_requirements。仅在剧本和当前片段范围内，合理增加反应镜头、停顿、细节和调度；打戏可结合人物能力与场景补全攻防过程、适当增加镜头数量和合理时长，但保留原事件和胜负结果；按相关场景增加镜头表现，不把要求机械重复到每镜；保持事件因果、人物动机及原台词，不新增剧情、角色或台词，不改输出schema。要求与剧本或模型硬限制冲突时，以剧本和硬限制为准。'
    if payload.get('timing_constraint'):
        task_instruction+='\n指定段落有独立的银幕时长预算timing_constraint，seconds是整段目标，part_seconds是本次片段建议分配的秒数，不能把整段时长误当一个shot时长。请展开为多个有实际动作变化、反应或机位意义的shots，满足累计时长；原文很短不代表表演很短。只计当前指定动作段落，不用前后其他剧情凑时间。台词仅按给定编号使用一次，无台词时line_ids为空；仍遵循每段模型时长上限。'
    messages = [{'role': 'system', 'content': task_instruction}, {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}]
    diag = task.setdefault('h3v2_diagnostics', [])
    errors = []
    for attempt in range(ATTEMPTS):
        t0 = time.time()
        resp = api.Q.text_request({'model': task['model'], 'messages': messages, **SAMPLING, 'max_tokens': 12000,
                                   'response_format': {'type': 'json_schema', 'json_schema': {'name': 'h3_structured_shots', 'schema': sch}},
                                   'chat_template_kwargs': {'enable_thinking': False}}, task)
        choice = resp['choices'][0]
        raw = re.sub(r'<think>.*?</think>', '', choice['message'].get('content') or '', flags=re.S)
        try:
            obj = json.loads(raw[raw.find('{'):raw.rfind('}') + 1])
        except ValueError as exc:
            obj = None
            errors = ['JSON 无法解析：' + str(exc) + ('（输出达到长度上限，请减少镜头内文字）' if choice.get('finish_reason') == 'length' else '')]
        else:
            obj = fix_cjk(autofix(obj, rules), cat)
            errors = resolve_lines(obj, chunk_lines, cat) if coverage else []
            drop_unused_props(obj); trim_refs(obj, cat); stretch_for_cps(obj, rules); split_overfull_speakers(obj, rules); trim_refs(obj, cat); stretch_for_cps(obj, rules)
            errors += [e for e in validate_rows(obj, cat, rules, chunk_lines, script_lines, coverage) if not (errors and e.startswith('遗漏剧本台词'))]
        diag.append({'chunk': label, 'attempt': attempt + 1, 'seconds': round(time.time() - t0, 1),
                     'finish_reason': choice.get('finish_reason'), 'errors': errors[:40]})
        del diag[:-200]
        if not errors:
            return obj['shots'], attempt + 1
        messages = messages[:2] + [{'role': 'assistant', 'content': raw[:24000]},
                                   {'role': 'user', 'content': '程序校验未通过，请逐条修正后重新返回本片段完整 JSON（全部 shot，不只改错的）：\n- ' + '\n- '.join(errors[:30])}]
    raise StructuredOutputError(f'{label} 经 {ATTEMPTS} 次校验仍不合格，原分镜未覆盖：' + '；'.join(errors[:6]))


def plan(api, p, task):
    import storyboard
    started = time.time()
    skill = task['storyboard_skill']
    mode, model = skill['video_mode'], skill['video_model']
    rules = model_rules(model)
    cat = catalog(p)
    if not cat:
        raise ValueError('请先提取或添加参考资产，再生成 H3 结构化分镜；无人物短片可使用场景或道具')
    script_lines = dialogue_lines(p['script'], cat)
    parts = segment_timing.partition(p,chunks)
    storyboard.progress(api, task, 'h3v2_profiles', 0, len(parts))
    profiles = asset_profiles(api, task, cat)
    shots = []
    timing_rows=[]
    previous = None
    stats = task.setdefault('h3v2_stats', {'chunks': []})
    for index, part in enumerate(parts):
        storyboard.progress(api, task, 'h3v2_planning', index, len(parts))
        label = f'片段{index + 1}/{len(parts)}（{part["heading"]}）'

        def ask(text, tag):
            chunk_lines = number_lines(dialogue_lines(text, cat))
            payload = {'task': '把 script_chunk 拆成视频 shots。只处理本片段，不要提前写后面的剧情。',
                       'video_model': model, 'video_model_rules': rules, 'scene_heading': part['heading'], 'scene_meta': part['scene_meta'],
                       'script_chunk': text, 'storyboard_requirements':p.get('storyboard_requirements',''), 'previous_shot': previous, 'assets': llm_catalog(cat),
                       'dialogue_in_chunk': llm_lines(chunk_lines, cat),'timing_constraint':part.get('timing_constraint')}
            return ask_rows(api, task, cat, rules, payload, chunk_lines, script_lines, True, 12, tag)
        skip_err = None
        try:
            rows, attempts = ask(part['text'], label)
        except StructuredOutputError as exc:
            # Bounded fallback: split the chunk in half once (smaller task), same validation, never relaxed.
            paras = [x for x in re.split(r'\n\s*\n', part['text']) if x.strip()]
            if len(paras) < 2:
                skip_err = str(exc)
                rows, attempts = [], ATTEMPTS
            else:
                half = max(1, len(paras) // 2)
                rows, attempts = [], ATTEMPTS
                try:
                    for k, text in enumerate(('\n\n'.join(paras[:half]), '\n\n'.join(paras[half:]))):
                        got, n = ask(text, f'{label}-拆分{k + 1}/2')
                        rows += got; attempts += n
                        previous = {'title': got[-1]['title'], 'description_zh': got[-1]['description_zh'][:200], 'cast': got[-1].get('cast'), 'scene': got[-1].get('scene')}
                except StructuredOutputError as exc2:
                    skip_err = str(exc2)
                    rows = []
        if skip_err is not None:
            skipped = task.setdefault('h3v2_skipped', [])
            skipped.append({'chunk': label, 'index': index, 'heading': part['heading'], 'error': skip_err[:500]})
            stats['chunks'].append({'chunk': label, 'attempts': attempts, 'shots': 0, 'status': 'skipped', 'error': skip_err[:300]})
            task['storyboard_draft'] = copy.deepcopy(shots)
            continue
        stats['chunks'].append({'chunk': label, 'attempts': attempts, 'shots': len(rows), 'status': 'ok'})
        for row in rows:
            if part.get('timing_constraint'):row['_timing_constraint_id']=part['timing_constraint']['id']
            timing_rows.append(row)
            shot = build_shot(api, p, to_plan(row, cat, profiles), row, mode, model)
            shots.append(shot)
        last = rows[-1]
        previous = {'title': last['title'], 'description_zh': last['description_zh'][:200],
                    'cast': last.get('cast'), 'scene': last.get('scene')}
        task['storyboard_draft'] = copy.deepcopy(shots)
    if p.get('segment_timings'):
        def extend_budget(budget,existing,seconds,count):
            storyboard.progress(api,task,'h3v2_timing',len(existing),math.ceil(budget['seconds']/rules['max']))
            payload={'task':'为指定动作段落补充新的中间镜头，放在已有结尾镜头之前；不要重演开头或终局，不新增事件、角色、台词。所有line_ids必须为空。用不同的观察与连贯动作扩展实际表演，不要复制旧镜头、静止凑时长或只写字幕。',
                'script_chunk':budget['quote'],'storyboard_requirements':p.get('storyboard_requirements',''),'timing_constraint':dict(budget,part_seconds=seconds),
                'existing_shots':[{'title':x['title'],'description':x['description_zh']} for x in existing],
                'assets':llm_catalog(cat),'dialogue_in_chunk':[],'video_model':model,'video_model_rules':rules}
            got,_=ask_rows(api,task,cat,rules,payload,[],script_lines,False,count,'扩展段落时长')
            if any(c.get('line_ids') for row in got for c in row['clips']):raise ValueError('扩展镜头不能重复原台词')
            return got
        timing_rows,reports=segment_timing.expand(p,timing_rows,rules,extend_budget)
        shots=[]
        for row in timing_rows:
            shot=build_shot(api,p,to_plan(row,cat,profiles),row,mode,model)
            if row.get('_timing_constraint_id'):
                shot['timing_constraint_id']=row['_timing_constraint_id']
                shot['timing_constraint_quote']=next(b['quote'] for b in p['segment_timings'] if b['id']==row['_timing_constraint_id'])
            shots.append(shot)
        task['segment_timing_report']=reports
    stats['seconds'] = round(time.time() - started, 1)
    stats['shots'] = len(shots)
    skipped = task.get('h3v2_skipped') or []
    stats['skipped'] = len(skipped)
    if skipped:
        note = '已跳过 %d/%d 个片段（其余已写入）：' % (len(skipped), len(parts)) + '；'.join(
            x['chunk'] + ' → ' + x['error'][:80] for x in skipped[:8])
        task.setdefault('storyboard_quality_notes', []).append({'stage': 'h3v2', 'reason': note})
        task['h3v2_warning'] = note
    if not shots:
        raise StructuredOutputError('全部 %d 个片段均校验失败，原分镜未覆盖。' % len(parts) + (
            '首条：' + skipped[0]['error'][:200] if skipped else ''))
    storyboard.progress(api, task, 'complete', len(shots), len(shots))
    return {'shots': shots}


def write_existing(api, p, task):
    """Rewrite prompts of selected shots. If a valid structured plan exists, re-render
    for the current model without the LLM; otherwise re-plan that one shot."""
    import storyboard
    shots = copy.deepcopy(p['shots'])
    selected = set(task['storyboard_shot_ids'])
    cat = catalog(p)
    by_id = {r['id']: r for r in cat}
    script_lines = dialogue_lines(p['script'], cat)
    profiles = None
    done = 0
    for shot in shots:
        if shot['id'] not in selected:
            continue
        storyboard.progress(api, task, 'h3v2_prompts', done, len(selected))
        mode, model = api.video_mode(shot, p), api.video_model(shot, p)
        rules = model_rules(model)
        plan_ = shot.get('h3_plan')
        if shot.get('prompt_format') == FORMAT and plan_ and not validate_plan(p, shot, plan_, rules):
            text = render(p, plan_, mode, model)
            shot.update(video_prompt=text, h3_rendered=text, prompt_video_model=model, prompt_video_mode=mode)
            shot.pop('prompt_stale', None)
        else:
            if profiles is None:
                profiles = asset_profiles(api, task, cat)
            handle = {r['id']: r['handle'] for r in cat}
            current = [{'asset': handle[a], 'look': next((l['handle'] for l in by_id[a]['looks'] if l['id'] == shot.get('character_looks', {}).get(a)), by_id[a]['default_look'])}
                       for a in shot.get('asset_ids', []) if a in by_id and by_id[a]['type'] == '角色']
            text = '标题：' + str(shot.get('title', '')) + '\n' + str(shot.get('description', '')) + '\n' + '\n'.join(
                str(x.get('speaker', '')) + '：' + str(x.get('text', '')) for x in shot.get('dialogue') or [] if isinstance(x, dict))
            lines = number_lines(dialogue_lines(text, cat))
            payload = {'task': '把这个已有镜头改写为 1 个 shot，保持剧情、台词与出场角色；放不下时缩短动作描写、合理分配 clip 时长。',
                       'video_model': model, 'video_model_rules': rules, 'script_chunk': text, 'storyboard_requirements':p.get('storyboard_requirements',''), 'current_cast': current,
                       'assets': llm_catalog(cat), 'dialogue_in_chunk': llm_lines(lines, cat)}
            rows, _ = ask_rows(api, task, cat, rules, payload, lines, script_lines, True, 1, '镜头“' + str(shot.get('title', ''))[:20] + '”')
            row = rows[0]
            new = build_shot(api, p, to_plan(row, cat, profiles), row, mode, model)
            for k in ('duration', 'asset_ids', 'character_looks', 'dialogue', 'video_prompt', 'h3_rendered', 'h3_plan',
                      'prompt_format', 'storyboard_scheme', 'prompt_video_model', 'prompt_video_mode'):
                shot[k] = new[k]
            shot.pop('prompt_stale', None)
        done += 1
    storyboard.progress(api, task, 'complete', done, len(selected))
    return {'shots': shots}


# ---------------------------------------------------------------- saved-shot validation & staleness
def validate_plan(p, shot, plan_, rules):
    errors = []
    assets = {a['id']: a for a in p['assets']}
    d = shot.get('duration')
    try:
        d = float(d)
    except (TypeError, ValueError):
        return ['时长无效']
    if abs(d - float(plan_.get('duration', 0))) > 0.05:
        errors.append(f'镜头时长 {d:g}s 与结构化计划 {plan_.get("duration")}s 不一致，需重写提示词')
    if not rules['min'] <= d <= rules['max'] or (rules['integer'] and d != int(d)):
        errors.append(f'当前视频模型（{rules["family"]}）要求时长 {rules["min"]}-{rules["max"]} 秒' + ('整数' if rules['integer'] else '') + f'，本镜 {d:g}s')
    if len(plan_.get('refs', [])) > MAX_REFS:
        errors.append(f'参考图超过 {MAX_REFS} 张')
    for aid in plan_.get('refs', []):
        if aid not in assets:
            errors.append('引用的资产已删除')
    for c in plan_.get('cast', []):
        a = assets.get(c['asset_id'])
        if a and c.get('look_id') and not any(l['id'] == c['look_id'] for l in a.get('looks', [])):
            errors.append((a.get('name') or '') + ' 的造型已删除')
    speakers = set()
    for c in plan_.get('clips', []):
        if c.get('line'):
            length = c['end'] - c['start']
            if length <= 0 or spoken_len(c['line']) / length > MAX_CPS + 1e-6:
                errors.append('台词语速超过 4 字/秒')
            speakers.add(tuple(sorted(c['speakers'])))
    if len(speakers) > MAX_SPEAKERS:
        errors.append('说话方超过 2 个')
    return errors


def stale_reason(p, shot, mode, model):
    if not str(shot.get('video_prompt') or '').strip():
        return None
    gen_model, gen_mode = shot.get('prompt_video_model'), shot.get('prompt_video_mode')
    if gen_model and gen_model != model:
        return f'提示词按 {gen_model} 编写，当前视频模型为 {model}，请重写提示词'
    if gen_mode and gen_mode != mode:
        return f'提示词按 {gen_mode} 方式编写，当前为 {mode}，请重写提示词'
    plan_ = shot.get('h3_plan')
    if shot.get('prompt_format') == FORMAT and plan_:
        try:
            if abs(float(shot.get('duration')) - float(plan_.get('duration'))) > 0.05:
                return '镜头时长已手动修改，结构化提示词的时间轴需要重写'
        except (TypeError, ValueError):
            return '镜头时长无效'
    return None


# ---------------------------------------------------------------- rendering
def _profile(plan_, aid, look_id=None):
    prof = plan_.get('profiles', {})
    return prof.get(profile_key(aid, look_id)) or prof.get(aid) or {}


def render(p, plan_, mode, model, order=None):
    """order: asset_id -> 1-based picture index of the images actually sent."""
    rules = model_rules(model)
    reference = mode in ('reference', 'video_reference') and rules['h3']
    refs = list(plan_['refs'])
    order = order or {aid: i + 1 for i, aid in enumerate(refs)}
    assets = {a['id']: a for a in p['assets']}
    looks = {c['asset_id']: c.get('look_id') for c in plan_.get('cast', [])}
    handles = plan_.get('handles', {})
    first_seen = set()
    S = {}

    def prof(aid):
        return _profile(plan_, aid, looks.get(aid))

    def label(aid, intro=True):
        if reference and aid in order:
            out = f'<Subject {order[aid]}>'
            if intro and aid not in first_seen:
                short = prof(aid).get('short')
                out += f' ({short})' if short else ''
            first_seen.add(aid)
            return out
        pr = prof(aid)
        if aid not in first_seen:
            first_seen.add(aid)
            return pr.get('en') or pr.get('short') or 'the person'
        return pr.get('short') or 'the person'

    def sub(text, intro=True):
        return HANDLE.sub(lambda m: label(handles[m[1]], intro) if m[1] in handles else m[0], str(text or ''))

    def speaker_ids(spk):
        for s in spk:
            if s not in S:
                S[s] = 'S' + str(len(S) + 1)
        return '(' + ','.join(S[s] for s in spk) + ')'

    shot_no = 0
    shot_texts = []
    appears = {}
    for i, c in enumerate(plan_['clips']):
        cut = i == 0 or c.get('new_cut')
        action = sub(c['action']).strip()
        if action and action[-1] not in '.!?"”':
            action += '.'
        camera = sub(c.get('camera') or 'static camera', False).strip().rstrip('.')
        size = (c.get('shot_size') or '').strip().rstrip('.')
        framing = camera if size.lower() in camera.lower() else (f'{size}, {camera}' if size else camera)
        article = 'an' if framing[:1].lower() in 'aeiou' else 'a'
        if cut:
            shot_no += 1
            head = f'[Shot {shot_no}] ' + (f'{article.capitalize()} {framing}. ' if shot_no == 1 else f'At {ts(c["start"])}, the shot cuts to {article} {framing}. ')
            shot_texts.append(head + action)
        elif i and size and size != (plan_['clips'][i - 1].get('shot_size') or ''):
            shot_texts[-1] += f' Then, the camera reframes to {article} {framing}. {action}'
        else:
            shot_texts[-1] += f' Then, {action[0].lower() + action[1:] if action else ""}'
        for aid in set(c['subjects']) | set(c['speakers']):
            appears.setdefault(aid, []).append(shot_no)
        if c.get('line'):
            spk = c['speakers']
            off = [s for s in spk if s not in c['subjects']]
            first = [s for s in spk if s not in S]
            who = ' and '.join(label(s) for s in spk) if len(spk) <= 2 else ', '.join(label(s) for s in spk[:-1]) + ' and ' + label(spk[-1])
            ids = speaker_ids(spk)
            verb = 'say together' if len(spk) > 1 else 'says'
            if off and len(off) == len(spk):
                verb += ' off-screen'
            voice = ''
            if len(spk) == 1 and first:
                v = prof(spk[0]).get('voice')
                voice = f', in {v},' if v else ''
            delivery = f', {c["delivery"].strip().rstrip(".,")}' if c.get('delivery') else ''
            line = c['line'].strip()
            shot_texts[-1] += f' {who} {ids}{voice} {verb}{delivery}: <d>[Chinese] {line}</d>'
    scene = plan_.get('scene')
    if scene:
        appears[scene] = list(range(1, shot_no + 1))
    look = sub(plan_.get('look_en', ''), False).strip()
    sound = sub(plan_.get('soundscape_en', ''), False).strip() or 'Quiet indoor room tone.'
    music = (plan_.get('music_en') or 'N/A').strip() or 'N/A'
    if reference:
        defs = []
        keep = []
        for aid in refs:
            if aid not in order:
                continue
            k = order[aid]
            a = assets.get(aid, {})
            en = (prof(aid).get('en') or TYPE_EN.get(a.get('type'), 'subject')).strip().rstrip('. ')
            kind = a.get('type')
            if kind == '场景':
                defs.append(f'<Subject {k}> is the environment shown in <Picture {k}>: {en}.')
                what = 'the spatial layout, materials, set dressing and lighting are retained'
            elif kind == '道具':
                defs.append(f'<Subject {k}> is the object shown in <Picture {k}>: {en}.')
                what = 'the shape, color and material are retained'
            else:
                defs.append(f'<Subject {k}> is the person shown in <Picture {k}>: {en}.')
                what = 'the identity, face, hairstyle and the selected outfit are retained'
            shots = sorted(set(appears.get(aid, []))) or [1]
            keep.append(f'<Subject {k}> (appears in ' + ', '.join(f'[Shot {n}]' for n in shots) + f'): fully_preserved - {what}.')
        first_seen.clear()
        summary = '[reference generation] ' + sub(plan_.get('summary_en', ''), False).strip()
        body = 'The target video is a live-action, photorealistic Chinese short-drama scene. ' + look + '\n' + '\n'.join(shot_texts)
        sections = [('subject_definitions', '\n'.join(defs) or 'N/A'), ('summary', summary), ('retention_analysis', '\n'.join(keep) or 'N/A'),
                    ('detailed_description', body), ('overall_soundscape', sound), ('non_diegetic_music', music)]
        return '\n\n'.join(k + ':\n' + v for k, v in sections)
    body = ' '.join(shot_texts)
    body = body.replace('[Shot 1] ', '[Shot 1] Live-action, photorealistic, ' + (look + ' ' if look else ''), 1)
    if rules['h3']:
        text = 'integrated_multimodal_description: ' + body + '\n\noverall_soundscape: ' + sound + '\n\nnon_diegetic_music: ' + music
        return FIRST_FRAME + '\n\n' + text if mode == 'first_frame' else text
    return body + ' Sound: ' + sound + (' Music: ' + music if music != 'N/A' else '')


def compile(p, shot, kind, inputs, mode, model):
    bindings = []
    order = {}
    for index, item in enumerate(inputs, 1):
        if item.get('url') and item.get('asset_id') and item['asset_id'] not in order:
            order[item['asset_id']] = index
            bindings.append({'label': item.get('name'), 'asset_id': item['asset_id'], 'look_id': item.get('look_id'),
                             'reference_index': index, 'subject_index': index, 'url': item['url'], 'version_id': item.get('version_id')})
    if kind != 'video':
        return shot.get(kind + '_prompt', ''), bindings
    text = shot.get('video_prompt', '')
    plan_ = shot.get('h3_plan')
    if plan_ and text == shot.get('h3_rendered'):
        rules = model_rules(model)
        errors = validate_plan(p, shot, plan_, rules)
        if errors:
            raise ValueError('结构化提示词与当前设置不符：' + '；'.join(errors) + '。请先“重写提示词”')
        if mode in ('reference', 'video_reference') and rules['h3']:
            missing = [aid for aid in plan_['refs'] if aid not in order]
            if missing:
                names = {a['id']: a.get('name', '') for a in p['assets']}
                raise ValueError('参考图缺失：' + '、'.join(names.get(a, a) for a in missing))
        return render(p, plan_, mode, model, order), bindings
    if HANDLE.search(text):
        raise ValueError('提示词中仍有未解析的 #A 编号，请重写提示词')
    return text, bindings


def bundle(api, p):
    mode = api.video_mode({}, p)
    model = p.get('video_model') or api.VIDEO_STRATEGIES[mode]['models'][0]
    rules = model_rules(model)
    text = instruction(rules)
    return {'name': 'shotdesk-storyboard', 'version': VERSION, 'format': FORMAT, 'scheme': FORMAT, 'video_mode': mode,
            'video_model': model, 'model_rules': rules, 'prompt_language': p.get('prompt_language') or 'zh',
            'sampling': SAMPLING, 'limits': {'max_refs': MAX_REFS, 'max_chars_per_second': MAX_CPS, 'max_speakers': MAX_SPEAKERS, 'attempts': ATTEMPTS},
            'official_sources': ['docs/skills/shotdesk-storyboard/references/h3-official-SKILL.md', 'docs/skills/shotdesk-storyboard/references/h3-ref-en.txt'],
            'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
