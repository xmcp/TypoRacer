#coding=utf-8
import cherrypy
from mako.template import Template
import os
import beatmap_parser
import zipfile
import configparser
import mimetypes
import requests
import io
import re
import json
import base64
import hashlib

osu_url_re=re.compile(r'^(?:https?://)?osu\.ppy\.sh/[sd]/(\d+)n?$')

class FakeFile:
    def __init__(self,content):
        self.file=io.BytesIO(content)

file_cache={}
def cache_file(content):
    md5=hashlib.new('md5',content).hexdigest()
    file_cache[md5]=content
    return md5

class Website:
    maps={}
    songs={}
    ind=0
    unknown_id=1

    def __init__(self):
        for filename in sorted(os.listdir('default_map')):
            try:
                self.load(FakeFile(open('default_map/'+filename,'rb').read()))
            except cherrypy.HTTPRedirect:
                pass

    @cherrypy.expose()
    def index(self):
        maplist=Template(filename='index.html',input_encoding='utf-8',output_encoding='utf-8')
        return maplist.render(maps=sorted(self.maps.values(),key=lambda x:x['ind']))

    @cherrypy.expose()
    def game(self,mapid):
        mapid=int(mapid)
        if mapid not in self.maps:
            raise cherrypy.NotFound()
        beatmap=self.maps[mapid]
        game=Template(filename='game.html',input_encoding='utf-8',output_encoding='utf-8')
        return game.render(
            title='%s (%s)'%(beatmap['title'],beatmap['version']),
            audio_url='/song/%d'%beatmap['songid'],
            beatmap=beatmap['beatmap'],
            bg_url='/img_cache/%s'%beatmap['background'],
            colors=beatmap['colors'],
            mapid=mapid,
        )

    @cherrypy.expose()
    def result(self,mapid,rep):
        mapid=int(mapid)
        rep=json.loads(base64.b64decode(rep.encode()).decode())
        scorepage=Template(filename='result.html',input_encoding='utf-8',output_encoding='utf-8')
        return scorepage.render(
            bg_url='/img_cache/%s'%self.maps[int(mapid)]['background'],
            rep=rep,
            title='%s (%s)'%(self.maps[mapid]['title'],self.maps[mapid]['version'])
        )
        
    @cherrypy.expose()
    def song(self,songid):
        cherrypy.response.headers['Content-Type']=self.songs[int(songid)]['type']
        return self.songs[int(songid)]['content']

    @cherrypy.expose()
    def img_cache(self,md5):
        if md5 in file_cache:
            return file_cache[md5]
        else:
            raise cherrypy.NotFound()

    @cherrypy.expose()
    def load(self,file):
        get_opt=lambda *_:beatmap_parser.get_opt(parser,*_)
        def unquote(x):
            return x[1:-1] if x[0]=='"' and x[-1]=='"' else x
        def case_insensitive_open(fn):
            return zipf.open(name_dict[fn.lower()])
        
        self.unknown_id+=1
        zipf=zipfile.ZipFile(file.file)
        name_dict={fn.lower():fn for fn in zipf.namelist()}
        audio_fn=None
        songid=None
        for beatmap_fn in filter(lambda fn:fn.endswith('.osu'),name_dict.values()):
            beatmap_str=zipf.open(beatmap_fn).read().decode('utf-8','ignore').partition('\n')[2]
            parser=configparser.ConfigParser(allow_no_value=True,delimiters=['\n'],comment_prefixes=['//'],strict=False)
            parser.optionxform=str # stop auto lowering key name
            parser.read_string(beatmap_str)
            if audio_fn is not None:
                assert audio_fn==get_opt('General','AudioFilename'), 'different audio filename in one map set'
            else:
                audio_fn=get_opt('General','AudioFilename')
            try:
                title=get_opt('Metadata','TitleUnicode')
            except AssertionError:
                title=get_opt('Metadata','Title')
            author=get_opt('Metadata','Creator')
            version=get_opt('Metadata','Version')
            try:
                mapid=int(get_opt('Metadata','BeatmapID'))
                assert mapid>0
            except AssertionError:
                mapid=-self.ind
            if songid is not None:
                if songid>0:
                    assert songid==int(get_opt('Metadata','BeatmapSetID')), 'different setid in one map set'
            else:
                try:
                    songid=int(get_opt('Metadata','BeatmapSetID'))
                    assert songid>0
                except AssertionError:
                    songid=-self.unknown_id
            for line in parser.options('Events'):
                splited=line.split(',')
                if splited[0]!='Video':
                    bg_fn=unquote(splited[2])
                    break
            else:
                raise AssertionError('no background image')
            if 'Colours' in parser.sections():
                colors=[list(map(int,line.partition(':')[2].strip().split(','))) for line in parser.options('Colours') if line]
            else:
                colors=[(255,128,0),(0,202,0),(18,124,255),(242,24,57)]

            self.maps[mapid]={
                'mapid':mapid,
                'songid':songid,
                'title':title,
                'author':author,
                'version':version,
                'beatmap':beatmap_parser.parse(beatmap_str),
                'background':cache_file(case_insensitive_open(bg_fn).read()),
                'ind':self.ind,
                'colors':colors,
            }
            self.ind+=1

        assert audio_fn is not None and songid is not None, 'no audio file or set id found'
        self.songs[songid]={
            'type':mimetypes.guess_type(audio_fn)[0],
            'content':case_insensitive_open(audio_fn).read(),
        }

        raise cherrypy.HTTPRedirect('/')

    @cherrypy.expose()
    def peppy(self,peppy_id,username,password):
        mat=osu_url_re.match(peppy_id)
        peppy_id=int(mat.groups()[0] if mat else peppy_id)

        s=requests.Session()
        # login
        s.post('https://osu.ppy.sh/forum/ucp.php?mode=login',data={
            'username':username,
            'password':password,
            'login':'Login'}
        ).raise_for_status()
        # download
        res=s.get('https://osu.ppy.sh/d/%dn'%peppy_id,verify=False)
        res.raise_for_status()
        assert not res.headers.get('Content-Type','').startswith('text/')
        # load
        self.load(FakeFile(res.content))


cherrypy.quickstart(Website(),'/',{
    'global': {
        'engine.autoreload.on': False,
        'server.socket_host': '0.0.0.0',
        'server.socket_port': int(os.environ.get('PORT',80)),
    },
    '/': {
        # 'tools.sessions.on': True,
        'tools.gzip.on': True,
        'tools.response_headers.on':True,
    },
    '/static': {
        'tools.staticdir.on':True,
        'tools.staticdir.dir':os.path.join(os.getcwd(),'static'),
        'tools.response_headers.headers': [
            ('Cache-Control','max-age=86400'),
        ],
    },
    '/img_cache': {
        'tools.response_headers.headers': [
            ('Cache-Control','max-age=8640000'),
        ],
    }
})