from typing import Dict, List
from abc import ABC, abstractmethod
from misc import exec_cmd

import os

langs = ['c', 'cpp']

class Compiler:
    name: str
    lang: str

    def __init__(self, name, lang):
        self.name = name
        self.lang = lang

    def create_object(output: str, source: str, params: Dict):
        pass

    def create_executable(output: str, objects: List[str], libs: List[str], params: Dict):
        pass

# Clang
clangpp = Compiler('clang++', 'cpp')
def clangpp_create_object(output, source, params):
    cmd = 'clang++ {2} -o {0} -c {1} {3} {4}'.format(
        output,
        source,
        '-g' if params.get('debug-symbols', 'false') == 'true' else '',
        ''.join([' -I %s' % file for file in params.get('includes', [])]),
        ''.join([' -D %s' % mac  for mac  in params.get('defines', [])]),
    )
    exec_cmd(cmd)
clangpp.create_object = clangpp_create_object
def clangpp_create_executable(output, objects, libs, params):
    cmd = 'clang++ {2} -o {0} {1} {3} {4} {5}'.format(
        output,
        ' '.join(objects),
        '-g' if params.get('debug-symbols', 'false') == 'true' else '',
        ''.join([' -I %s' % file for file in params.get('includes', [])]),
        ''.join([' -D %s' % mac  for mac  in params.get('defines', [])]),
        ''.join([' -L {} -l:{}'.format(os.path.dirname(path), os.path.basename(path)) for path in libs]),   # That colon in `-l:` is important because it disables the lib-prefix nonsense
    )
    exec_cmd(cmd)
clangpp.create_executable = clangpp_create_executable

compilers = [clangpp]

def find(name=None, lang=None):
    try:
        if name:
            return next(c for c in compilers if c.name == name)
        elif lang:
            return next(c for c in compilers if c.lang == lang)
    except StopIteration:
        raise KeyError('No compiler found for ' + 'name "%s"' % name if name else 'language "%s"' % lang)

# gcc -shared -fPIC -Wl,-soname,./libhello.so.1 -o libhello.so.1.0.0 libhello.o -lc
