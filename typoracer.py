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

osu_url_re=re.compile(r'^(?:https?://)?osu\.ppy\.sh/[sd]/(\d+)n?$')

class Website:
    maps={}
    songs={}
    ind=0

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
            bg_url='/bg_img/%d'%mapid,
        )

    @cherrypy.expose()
    def song(self,songid):
        cherrypy.response.headers['Content-Type']=self.songs[int(songid)]['type']
        return self.songs[int(songid)]['content']

    @cherrypy.expose()
    def bg_img(self,mapid):
        cherrypy.response.headers.pop('Content-Type',None)
        return self.maps[int(mapid)]['background']

    @cherrypy.expose()
    def load(self,file):
        def get_opt(section,option):
            for line in parser.options(section):
                k,_,v=line.partition(':')
                if k.strip()==option:
                    return v.strip()
            raise AssertionError('bad beatmap file')

        def unquote(x):
            return x[1:-1] if x[0]=='"' and x[-1]=='"' else x

        zipf=zipfile.ZipFile(file.file)
        audio_fn=None
        songid=None
        for beatmap_fn in filter(lambda fn:fn.endswith('.osu'),zipf.namelist()):
            beatmap_str=zipf.open(beatmap_fn).read().decode('utf-8','ignore').partition('\n')[2]
            parser=configparser.ConfigParser(allow_no_value=True,delimiters=['\n'],comment_prefixes=['//'])
            parser.optionxform=str # stop auto lowering key name
            parser.read_string(beatmap_str)
            if audio_fn is not None:
                assert audio_fn==get_opt('General','AudioFilename'), 'different audio filename in one map set'
            else:
                audio_fn=get_opt('General','AudioFilename')
            title=get_opt('Metadata','TitleUnicode')
            author=get_opt('Metadata','Creator')
            version=get_opt('Metadata','Version')
            mapid=int(get_opt('Metadata','BeatmapID'))
            if songid is not None:
                assert songid==int(get_opt('Metadata','BeatmapSetID')), 'different setid in one map set'
            else:
                songid=int(get_opt('Metadata','BeatmapSetID'))
            bg_fn=unquote(parser.options('Events')[0].split(',')[2])

            self.maps[mapid]={
                'mapid':mapid,
                'songid':songid,
                'title':title,
                'author':author,
                'version':version,
                'beatmap':beatmap_parser.parse(beatmap_str),
                'background':zipf.open(bg_fn).read(),
                'ind':self.ind
            }
            self.ind+=1

        assert audio_fn is not None and songid is not None, 'no audio file or set id found'
        self.songs[songid]={
            'type':mimetypes.guess_type(audio_fn)[0],
            'content':zipf.open(audio_fn).read(),
        }

        raise cherrypy.HTTPRedirect('/')

    @cherrypy.expose()
    def peppy(self,peppy_id,username,password):
        class FakeFile:
            def __init__(self,content):
                self.file=io.BytesIO(content)

        mat=osu_url_re.match(peppy_id)
        peppy_id=int(mat.groups()[0] if mat else peppy_id)
        s=requests.Session()
        s.post('https://osu.ppy.sh/forum/ucp.php?mode=login',data={
            'username':username,
            'password':password,
            'login':'Login'}
        ).raise_for_status()
        res=s.get('https://osu.ppy.sh/d/%dn'%peppy_id,verify=False)
        res.raise_for_status()
        assert not res.headers.get('Content-Type','').startswith('text/')
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
    }
})