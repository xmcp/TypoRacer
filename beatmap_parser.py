#coding=utf-8
import configparser
import json

def _parse_meters(lines):
    return list(map(lambda splited:(int(splited[0]),int(splited[2])),sorted(
        (line.split(',') for line in lines if line),
        key=lambda x:int(x[0]) #offset
    )))

def _parse_hit_objs(lines,meters):
    hit_obj_lines=sorted(
        (line.split(',') for line in lines if line),
        key=lambda x:int(x[2]) #time
    )
    meter_ind=0
    meters.append((2147483647,0))
    for splited in hit_obj_lines:
        _x,_y,time,typ,_hitsound,*args=splited
        typ=int(typ)
        time=int(time)

        while meters[meter_ind+1][0]<time:
            meter_ind+=1

        if typ in [1,5]: #circle
            yield {
                'time': time,
                'type': 'circle',
            }
        elif typ in [2,6]: #slider
            repeat_count=int(args[1])
            time_delta=float(args[2])*meters[meter_ind][1]
            yield {
                'time': time,
                'type': 'slider',
                'stop_time': time+time_delta*repeat_count,
            }
            for ind in range(repeat_count-1):
                yield {
                    'time': time+time_delta*(ind+1),
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
    meters=_parse_meters(parser.options('TimingPoints'))
    hit_objs=_parse_hit_objs(parser.options('HitObjects'),meters)
    return json.dumps(list(hit_objs))