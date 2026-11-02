"""Initialize local ignored data; never read or copy existing personal records."""
import argparse
from library import ROOT
from sample_data import prepare

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo',action='store_true',help='Use explicitly synthetic projects and papers instead of an empty library.')
    args=parser.parse_args()
    try:
        data=prepare(ROOT,demo=args.demo,assets=False)
        print(f"Initialized {len(data['projects'])} projects and {len(data['papers'])} references locally. No schedules or source connections created.")
    except (ValueError,OSError) as error:parser.exit(1,str(error)+'\n')
