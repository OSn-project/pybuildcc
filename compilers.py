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

    def create_object(self, output: str, source: str, params: Dict):
        pass

    def create_executable(self, output: str, objects: List[str], libs: List[str], params: Dict):
        pass

    def create_shlib(self, output: str, objects: List[str], libs: List[str], params: Dict):
        pass

# Clang
class Clang:
    def __init__(self, cpp=False):
        if cpp:
            self.lang = 'cpp'
            self.name = 'clang++'
            self.is_cpp = True
        else:
            self.lang = 'c'
            self.name = 'clang'
            self.is_cpp = False

    def create_object(self, output, source, params):
        cmd = '{ccname} -o {out} -c{g_param}{fpic_param} {src} {inc_dirs} {defines} {opts}'.format(
            ccname = 'clang++' if self.is_cpp else 'clang',
            out=output,
            src=source,
            g_param=' -g' if params.get('debug-symbols', 'false') == 'true' else '',
            fpic_param=' -fPIC' if params.get('for-shlib', False) else '',
            inc_dirs=''.join([' -I %s' % file for file in params.get('includes', [])]),
            defines=''.join([' -D %s' % mac  for mac  in params.get('defines', [])]),
            opts=' '.join(params.get('opts', [])),
        )
        exec_cmd(cmd)

    def create_executable(self, output, objects, libs, params):
        cmd = '{ccname} -{g_param}o {out} {objs} {inc_dirs} {defines} {link_libs} {opts}'.format(
            ccname = 'clang++' if self.is_cpp else 'clang',
            out=output,
            objs=' '.join(objects),
            g_param='-g' if params.get('debug-symbols', 'false') == 'true' else '',
            inc_dirs=''.join([' -I %s' % file for file in params.get('includes', [])]),
            defines=''.join([' -D %s' % mac  for mac  in params.get('defines', [])]),
            link_libs=''.join([' -L {} -l:{} {opts}'.format(os.path.dirname(path), os.path.basename(path)) for path in libs]),   # That colon in `-l:` is important because it disables the lib-prefix nonsense
            opts=' '.join(params.get('opts', [])),
        )
        exec_cmd(cmd)

    def create_shlib(self, output, objects, libs, params):
        cmd = '{ccname} -shared -{g_param}o {out} {objs} {inc_dirs} {defines} {link_libs} {opts}'.format(
            ccname = 'clang++' if self.is_cpp else 'clang',
            out=output,
            objs=' '.join(objects),
            g_param='-g' if params.get('debug-symbols', 'false') == 'true' else '',
            inc_dirs=''.join([' -I %s' % file for file in params.get('includes', [])]),
            defines=''.join([' -D %s' % mac  for mac  in params.get('defines', [])]),
            link_libs=''.join([' -L {} -l:{} {opts}'.format(os.path.dirname(path), os.path.basename(path)) for path in libs]),   # That colon in `-l:` is important because it disables the lib-prefix nonsense
            opts=' '.join(params.get('opts', [])),
        )
        exec_cmd(cmd)

compilers = [Clang(cpp=True), Clang(cpp=False)]

def find(name=None, lang=None):
    try:
        if name:
            return next(c for c in compilers if c.name == name)
        elif lang:
            return next(c for c in compilers if c.lang == lang)
    except StopIteration:
        raise KeyError('No compiler found for ' + 'name "%s"' % name if name else 'language "%s"' % lang)

# gcc -shared -fPIC -Wl,-soname,./libhello.so.1 -o libhello.so.1.0.0 libhello.o -lc
