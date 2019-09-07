"""
Overview
========

This plugin does autocompletion using ycmd.


Key-Commands
============

Namespace: ycmd

Mode: INSERT
Event: <Control-Key-period>
Description: Open the completion window with possible python words for
completion.

"""

from vyapp.completion import CompletionWindow, TextWindow
from base64 import b64encode, b64decode
from vyapp.plugins import ENV
from tempfile import NamedTemporaryFile
from subprocess import Popen, PIPE
from vyapp.areavi import AreaVi
from urllib.parse import urlparse
from os.path import join, dirname
import requests
import hashlib
import atexit
import hmac
import json
import time
import os

HMAC_LENGTH  = 16
IDLE_SUICIDE = 10800  # 3 hours
MAX_WAIT     = 5

class YcmdServer:
    def __init__(self, path, port, settings_file, extra_file):
        self.settings_file = settings_file
        self.extra_file    = extra_file ###
        self.settings      = None
        self.path          = path
        self.port          = port
        self.url           = 'http://127.0.0.1:%s' % port 
        self.cmd           = 'python -m %s --port %s --options_file %s'
        self.hmac_secret   = os.urandom(HMAC_LENGTH)
        self.hmac_secret   = str(b64encode(self.hmac_secret), 'utf-8')

        with open(self.settings_file) as fd:
          self.settings = json.loads(fd.read())

        self.settings[ 'hmac_secret' ] = self.hmac_secret
        with NamedTemporaryFile(mode = 'w+', delete = False) as tmpfile:
            json.dump(self.settings, tmpfile)

        self.daemon = Popen(self.cmd % (self.path, self.port,
        tmpfile.name), shell=1, encoding='utf-8')
        atexit.register(self.daemon.terminate)

    def completions(self, line, col, path, data, dir, target=None, cmdargs=None):
        data = {
       'line_num': line,
       'column_num': col,
       'filepath': path,
       'file_data': data
        }

        data = json.dumps(data, ensure_ascii = False)

        url = '%s/completions' % self.url
        hmac_secret = self.hmac_req('POST', '/completions', data, self.hmac_secret)
        data = data.encode('utf-8')

        headers = {
            'X-Ycm-Hmac': hmac_secret,
            'content-type': 'application/json',
        }
        print('hmac is', hmac_secret)
        req = requests.post(url, data=data, headers=headers)
        print(req.headers)
        print(req.json())

    def hmac_req(self, method, path, body, hmac_secret):
        """
        Calculate hmac for request. The algorithm is based on what is seen
        in https://github.com/ycm-core/ycmd/blob/master/examples/example_client.py
        at CreateHmacForRequest function.
        """

        # method      = bytes(method, encoding = 'utf-8')
        # path        = bytes(path, encoding = 'utf-8')
        # body        = bytes(body, encoding = 'utf-8')
        # hmac_secret = bytes(hmac_secret, encoding = 'utf-8' )
        hmac_secret = bytes(hmac_secret, encoding = 'utf-8' )
        method      = bytes(method, encoding = 'utf-8' )
        path        = bytes(path, encoding = 'utf-8' )
        body        = bytes(body, encoding = 'utf-8' )

        method = bytes(hmac.new(hmac_secret, 
        method, digestmod = hashlib.sha256).digest())

        path = bytes(hmac.new(hmac_secret, 
        path, digestmod = hashlib.sha256).digest())

        body = bytes(hmac.new(hmac_secret, 
        body, digestmod = hashlib.sha256).digest())

        joined = bytes().join((method, path, body))

        data = bytes(hmac.new(hmac_secret, joined, 
        digestmod = hashlib.sha256).digest())

        return str(b64encode(data), 'utf8')

class YcmdWindow(CompletionWindow):
    """
    """

    def __init__(self, area, server, *args, **kwargs):
        source      = area.get('1.0', 'end')
        line, col   = area.indcur()

        data = {area.filename: {'filetypes': ['python'], 'contents': source}}
        completions = server.completions(line, col, area.filename, data, dirname(area.filename))

        CompletionWindow.__init__(self, area, completions, *args, **kwargs)

class YcmdCompletion:
    server = None
    def __init__(self, area):

        completions = lambda event: YcmdWindow(event.widget, self.server)

        area.install('ycmd', ('INSERT', 
        '<Control-Key-period>', completions))

    @classmethod
    def setup(cls, path, port=43247):
        settings_file = join(dirname(__file__),  'default_settings.json')
        cls.server = YcmdServer(path, port,  settings_file, '')

install = YcmdCompletion

