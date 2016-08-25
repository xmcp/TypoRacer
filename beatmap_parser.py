#coding=utf-8
import configparser
import json

def _parse_bpm(lines):
    bpm=list(map(lambda splited:[int(splited[0]),float(splited[1]),int(splited[6]),int(splited[2])],sorted(
        (line.split(',') for line in lines if line),
        key=lambda x:int(x[0]) #offset
    ))) # list of (offset,mspb,inherited,meters)
    cur_mspb=0
    for dat in bpm:
        if dat[1]<0:
            dat[1]=cur_mspb*(-dat[1])/100
        if dat[2]:
            cur_mspb=dat[1]
    return bpm
    
def _parse_hit_objs(lines,bpm):
    hit_obj_lines=sorted(
        (line.split(',') for line in lines if line),
        key=lambda x:int(x[2]) #time
    )
    bpm_ind=0
    bpm.append((2147483647,1,0,1))
    for splited in hit_obj_lines:
        _x,_y,time,typ,_hitsound,*args=splited
        typ=int(typ)
        time=int(time)

        while bpm[bpm_ind+1][0]<time:
            bpm_ind+=1

        if typ in [1,5]: #circle
            yield {
                'time': time,
                'type': 'circle',
            }
        elif typ in [2,6]: #slider
            repeat_count=int(args[1])
            time_delta=float(args[2])*bpm[bpm_ind][3]*repeat_count-bpm[bpm_ind][1]/bpm[bpm_ind][3]
            yield {
                'time': time,
                'type': 'slider',
                'stop_time': time+time_delta,
            }
            for ind in range(repeat_count-1):
                yield {
                    'time': time+time_delta*(ind+1)/repeat_count,
                    'type': 'circle',
                }
        elif typ in [8,12]: #spinner
            yield {
                'time': time,
                'type': 'spinner',
                'stop_time': int(args[0]),
            }


def parse(content):
    parser=configparser.ConfigParser(allow_no_value=True,delimiters=['\n'],comment_prefixes=[])
    parser.read_string(content.partition('\n')[2])
    bpm=_parse_bpm(parser.options('TimingPoints'))
    hit_objs=_parse_hit_objs(parser.options('HitObjects'),bpm)
    return json.dumps(list(hit_objs))