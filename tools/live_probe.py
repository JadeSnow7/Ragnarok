#!/usr/bin/env python3
"""Generate exactly one real candidate, or apply a separately reviewed exact plan."""
import argparse
import json
from pathlib import Path
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from live_executor import LiveHandoff
from app import ROOT
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data-dir',type=Path,default=ROOT/'var/live-proof')
action=parser.add_mutually_exclusive_group(required=True)
action.add_argument('--generate',action='store_true')
action.add_argument('--show',metavar='TASK_ID')
action.add_argument('--approve',metavar='TASK_ID')
parser.add_argument('--plan-digest')
parser.add_argument('--revision',type=int)
args=parser.parse_args()
if args.approve and (not args.plan_digest or args.revision is None):
    parser.error('Approval requires the exact reviewed --plan-digest and --revision')
app=LiveHandoff(ROOT,args.data_dir,live_enabled=True)
try:
    if args.generate:
        doc,_=app.create({'mode':'live','recipe':'todo-persistence-v1',
          'objective':'Fix Todo checkbox state lost on page reload. Preserve other store behavior; do not modify tests.'},uuid.uuid4().hex)
    else:
        doc=app.get(args.approve or args.show)
        if args.approve:
            # Deterministic retry key: the identical approval can never launch a second run.
            doc,_=app.decide(doc['id'],{'decision':'approve','revision':args.revision,
                            'plan_digest':args.plan_digest},'probe-approve-'+doc['id'])
    for thread in app.threads: thread.join()
    doc=app.get(doc['id'])
    print(json.dumps(doc,ensure_ascii=False,indent=2))
    if doc['state'] in {'failed','unknown','cancelled'}: sys.exit(1)
finally: app.close()
