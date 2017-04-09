#coding=utf-8
import configparser
import json

def get_opt(parser,section,option):
    for line in parser.options(section):
        k,_,v=line.partition(':')
        if k.strip()==option:
            return v.strip()
    raise AssertionError('option not found')

def _parse_bpm(lines):
    bpm=list(map(lambda splited:[int(splited[0]),float(splited[1]),int(splited[6])],sorted(
        (line.split(',') for line in lines if line),
        key=lambda x:int(x[0]) #offset
    ))) # list of (offset,mspb,inherited)
    cur_mspb=0
    for dat in bpm:
        if dat[1]<0:
            dat[1]=cur_mspb*(-dat[1])/100
        if dat[2]:
            cur_mspb=dat[1]
    return bpm

def _parse_hit_objs(lines,bpms,slider_speed):
    hit_obj_lines=sorted(
        (line.split(',') for line in lines if line),
        key=lambda x:int(x[2]) #time
    )
    bpm_ind=0
    bpms.append((2147483647,1,0,1))

    for splited in hit_obj_lines:
        _x,_y,time,typ,_hitsound,*args=splited
        typ=int(typ)%16
        time=int(time)

        while bpms[bpm_ind+1][0]<time:
            bpm_ind+=1

        if typ in [1,5]: #circle
            yield {
                'time': time,
                'type': 'circle',
                'newcombo': bool(typ&4),
            }
        elif typ in [2,6]: #slider
            repeat_count=int(args[1])
            time_delta=float(args[2])*bpms[bpm_ind][1]/slider_speed
            yield {
                'time': time,
                'type': 'slider',
                'stop_time': time+time_delta*repeat_count,
                'newcombo': bool(typ&4),
            }
            for ind in range(repeat_count-1):
                yield {
                    'time': time+time_delta*(ind+1),
                    'type': 'circle',
                    'newcombo': False,
                }
        elif typ in [8,12]: #spinner
            yield {
                'time': time,
                'type': 'spinner',
                'stop_time': int(args[0]),
                'newcombo': True,
            }
        elif typ==-233: #text
            yield {
                'time': time,
                'type': 'text',
                'text': ','.join(args),
            }
        else:
            raise AssertionError('bad hitobj type: %d'%typ)


def parse(content):
    parser=configparser.ConfigParser(allow_no_value=True,delimiters=['\n'],comment_prefixes=['//'],strict=False)
    parser.optionxform=str # stop auto lowering key name
    parser.read_string(content.partition('\n')[2])
    slider_speed=float(get_opt(parser,'Difficulty','SliderMultiplier'))*100
    bpms=_parse_bpm(parser.options('TimingPoints'))
    hit_objs=_parse_hit_objs(parser.options('HitObjects'),bpms,slider_speed)
    return json.dumps(list(hit_objs))
