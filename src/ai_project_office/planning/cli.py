from __future__ import annotations
import argparse, json
from .baseline import assess_baseline, assessment_to_dict
from .service import load_schedule

def main(argv=None):
    parser=argparse.ArgumentParser(prog="ai-project-office-planning")
    sub=parser.add_subparsers(dest="command",required=True)
    b=sub.add_parser("baseline",help="Audit a baseline programme")
    b.add_argument("path")
    b.add_argument("--excel-map",default=None)
    b.add_argument("--long-duration-days",type=float,default=30.0)
    args=parser.parse_args(argv)
    if args.command=="baseline":
        schedule=load_schedule(args.path, excel_map=args.excel_map)
        result=assessment_to_dict(assess_baseline(schedule,args.long_duration_days))
        print(json.dumps(result,indent=2,default=str))
        return 0

if __name__=="__main__":
    raise SystemExit(main())
