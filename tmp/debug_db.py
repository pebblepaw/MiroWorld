import sqlite3, json, re
db = sqlite3.connect('backend/data/simulation.db')
db.row_factory = sqlite3.Row
sid = 'session-819ca44a'

# Check approval rate distribution from checkpoints
for kind in ['baseline', 'final']:
    cps = db.execute(
        "SELECT agent_id, stance_json FROM simulation_checkpoints WHERE session_id=? AND checkpoint_kind=?",
        (sid, kind)
    ).fetchall()
    scores = []
    for cp in cps:
        data = json.loads(cp['stance_json'])
        ma = data.get('metric_answers', {})
        val = str(ma.get('approval_rate', ''))
        match = re.match(r'(\d+(?:\.\d+)?)', val.strip())
        if match:
            scores.append(float(match.group(1)))
    if scores:
        avg = sum(scores) / len(scores)
        sup = sum(1 for s in scores if s >= 7)
        neu = sum(1 for s in scores if 5 <= s < 7)
        dis = sum(1 for s in scores if s < 5)
        print(f'{kind}: {len(scores)} vals, avg={avg:.1f}, sup={sup}, neu={neu}, dis={dis}')
    else:
        print(f'{kind}: no parseable values')

# Check approval_of_initiatives yes/no
for kind in ['baseline', 'final']:
    cps = db.execute(
        "SELECT stance_json FROM simulation_checkpoints WHERE session_id=? AND checkpoint_kind=?",
        (sid, kind)
    ).fetchall()
    yes_n = sum(1 for cp in cps if str(json.loads(cp['stance_json']).get('metric_answers', {}).get('approval_of_initiatives', '')).strip().lower() == 'yes')
    no_n = sum(1 for cp in cps if str(json.loads(cp['stance_json']).get('metric_answers', {}).get('approval_of_initiatives', '')).strip().lower() == 'no')
    print(f'{kind} initiatives: yes={yes_n}, no={no_n}')

# Check agents table opinion_pre/post
agents = db.execute('SELECT agent_id, opinion_pre, opinion_post FROM agents WHERE simulation_id=?', (sid,)).fetchall()
print(f'\nAgents table: {len(agents)} agents, sample pre={agents[0]["opinion_pre"]}, post={agents[0]["opinion_post"]}')
