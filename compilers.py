from typing import Dict, List
from abc import ABC, abstractmethod
from errors import PlatformError
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
    def __init__(self, cpp=False):  # clang can compile both C and C++, so we need to register it twice with different names. You can see this done further down.
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
            link_libs=''.join([' -Wl,-rpath,"{dir}" -L {dir} -l:{file}'.format(dir=os.path.dirname(path), file=os.path.basename(path)) for path in libs]),   # That colon in `-l:` is important because it disables the lib-prefix nonsense
            opts=' '.join(params.get('opts', [])),
        )
        exec_cmd(cmd)
    # https://stackoverflow.com/questions/12637841/what-is-the-soname-option-for-building-shared-libraries-for
    def create_shlib(self, output, objects, libs, params):
        cmd = '{ccname} -shared -{g_param}o {out} {objs} {inc_dirs} {defines} {link_libs} {opts}'.format(
            ccname = 'clang++' if self.is_cpp else 'clang',
            out=output,
            objs=' '.join(objects),
            g_param='-g' if params.get('debug-symbols', 'false') == 'true' else '',
            inc_dirs=''.join([' -I %s' % file for file in params.get('includes', [])]),
            defines=''.join([' -D %s' % mac  for mac  in params.get('defines', [])]),
            link_libs=''.join([' -Wl,-rpath,"{dir}" -L {dir} -l:{file}'.format(dir=os.path.dirname(path), file=os.path.basename(path)) for path in libs]),   # That colon in `-l:` is important because it disables the lib-prefix nonsense
            opts=' '.join(params.get('opts', [])),
        )
        exec_cmd(cmd)

# Watcom

import os
import glob
from misc import log

class Watcom:                           # Tested with OpenWatcom 1.9
    def __init__(self, cpp=False):
        if cpp:
            self.lang = 'cpp'
            self.name = ''
            self.is_cpp = True
        else:
            self.lang = 'c'
            self.name = 'watcom'
            self.is_cpp = False

    def create_object(self, output, source, params):
        tmp_output = 'OUT.OBJ'
        cmd = 'wcl /c {src} /fo={output} {debug} {defines} {inc_dirs} {opts}'.format(
            src=Watcom.path_to_dos(source),
            output=tmp_output,
            debug='/d2' if params.get('debug-symbols', 'false') == 'true' else '',
            inc_dirs=' '.join(['/i=%s' % Watcom.path_to_dos(file) for file in params.get('includes', [])]),
            defines=' '.join(['/d%s' % mac  for mac  in params.get('defines', [])]),
            opts=' '.join(params.get('opts', [])),
        )
        self.dosbox_exec(cmd)

        # We don't necessarily need to know the exact output name if it's longer than 8 chars (because DOS), so we save it under a temporary name and copy it in Linux afterwards.
        exec_cmd(f'mv {tmp_output} {output}')

    def create_executable(self, output, objects, libs, params):
        tmp_output = 'OUT.EXE'
        cmd = 'wcl /l=dos /fe={output} {objs} {opts}'.format(
            objs=' '.join(Watcom.path_to_dos(o) for o in objects),
            output=tmp_output,
            link_libs=''.join([' -Wl,-rpath,"{dir}" -L {dir} -l:{file}'.format(dir=os.path.dirname(path), file=os.path.basename(path)) for path in libs]),   # That colon in `-l:` is important because it disables the lib-prefix nonsense
            opts=' '.join(params.get('opts', [])),
        )
        self.dosbox_exec(cmd)
        exec_cmd(f'mv {tmp_output} {output}')

    def create_shlib(self, output: str, objects: List[str], libs: List[str], params: Dict):
        pass

    @staticmethod
    def dosbox_exec(cmd):
        commands = [f'mount W "{os.getcwd()}"', 'W:', cmd, 'exit']  # These run in DOS
        dosboxcmd = 'dosbox ' + ' '.join('-c "{}"'.format(doscmd.replace('"', '\\"')) for doscmd in commands)

        log(2, cmd)
        log(3, "Final DOSBOX command is:\n" + dosboxcmd)
        os.system(dosboxcmd)

    @staticmethod
    def path_to_dos(path, pathbase=''):  # path needs to be absolute and every dir needs to be accessible.
        in_pathelts  = path.split('/')
        out_pathelts = []

        for i in range(len(in_pathelts)):
            pathelt = in_pathelts[i]

            if pathelt.count('.') > 1:
                raise PlatformError('DOS file and directory names can contain only one `.`. Problem in this path:\n\t' + path, compiler='watcom')

            # dir = pathbase + '/'.join(in_pathelts[:i])
            #
            # # Find files starting with the same 8 chars. Files go first, then dirs
            # competitors_files = [p for p in glob.glob(pathelt[:8]+'*') if os.path.isfile(p)]
            # competitors_dirs  = [p for p in glob.glob(pathelt[:8]+'*') if os.path.isdir(p)]
            # competitors = sorted(competitors_files) + sorted(competitors_dirs)
            #
            # out_pathelts.append(pathelt[:6] + '~')  # Nope. What if it goes up to 13? Find what the official ordering is.

            if pathelt.count('.') == 0:
                pathelt += '.'  # Just make an empty extension if there isn't one

            basename, ext = pathelt.split('.')

            if len(basename) > 8:
                basename = basename[:6] + '~1'

            out_pathelts.append((basename + ('.' + ext[:3] if ext != '' else '')).upper())

        return '\\'.join(out_pathelts)


#wcl /c HELLO.C
#wcl /l=dos /fe=BLARG.EXE HELLO.OBJ
#

compilers = [Clang(cpp=True), Clang(cpp=False), Watcom(cpp=False)]

def find(name=None, lang=None):
    try:
        if name:
            return next(c for c in compilers if c.name == name)
        elif lang:
            return next(c for c in compilers if c.lang == lang)
    except StopIteration:
        raise KeyError('No compiler found for ' + 'name "%s"' % name if name else 'language "%s"' % lang)

# gcc -shared -fPIC -Wl,-soname,./libhello.so.1 -o libhello.so.1.0.0 libhello.o -lc
