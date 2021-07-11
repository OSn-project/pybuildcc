import xml.etree.cElementTree as ET
from typing import Dict, List
from tasks import Task
from filegens import FileGenTask
from misc import log, parse_preset, update_preset, untempl, flatten
from errors import ParseError
import itertools

import compilers

class ObjectTask(FileGenTask):  # Inherits Task
    sources: List[str]
    file: str

    output: List[str]

    compiler: compilers.Compiler
    params: Dict

    _preset_name: str   # Due to implementation this has to be stored until self.run() is called. (only then is `project` passed to us)

    def __init__(self, node: ET.Element, props: Dict, **kwargs):

        filesets = kwargs['filesets']

        if 'source' in node.attrib:     # some old files may have these
            raise ParseError('`source` attribute is deprecated. Switch to `src`.')
        if 'source-set' in node.attrib:
            raise ParseError('`source-set` attribute is deprecated. Switch to `src-set`.')

        if 'src' in node.attrib:
            self.source = [untempl(node.attrib['src'], props)]
        elif 'src-set' in node.attrib:
            self.source = filesets[node.attrib['src-set']].get_files()
        else:
            self.source = None

        self.file   = untempl(node.attrib['file'], props)   if 'file'   in node.attrib else None  # file overrides source if specified

        if self.file:
            self.output = [self.file]
        elif 'output' in node.attrib:
            self.output = [untempl(node.attrib['output'], props)]
        else:
            self.output = [path + '.o' for path in self.source]

        self.compiler = compilers.find(
            name=node.attrib['compiler'] if 'compiler' in node.attrib else None, # name overrides lang if specified
            lang=node.attrib['lang']     if 'lang'     in node.attrib else None
        )

        self._preset_name = node.attrib['preset'] if 'preset' in node.attrib else None
        self.params = parse_preset(node, props)

        self.for_shlib = False

    def run(self, project):
        # Apply preset
        if self._preset_name:
            preset = project.presets[self._preset_name]
            preset = update_preset(preset, self.params)
            self.params = preset

        if not self.file:
            for i in range(len(self.source)):
                log(1, 'compile {} -> {}'.format(self.source[i], self.output[i]))
                self.compiler.create_object(self.output[i], self.source[i], self.params)

    def get_files(self):
        return self.output

    @property
    def for_shlib(self) -> bool:
        return self.params.get('for-shlib', False)
    @for_shlib.setter
    def for_shlib(self, val: bool):
        self.params['for-shlib'] = val

    def __repr__(self):
        if self.file:
            return self.file
        else:
            return 'compile(' + ', '.join(['{} -> {}'.format(self.source[i], self.output[i]) for i in range(len(self.source))]) + ')'

class BinaryTask(Task):
    output: str

    objects: List[ObjectTask]
    linked_libs: List[str]

    compiler: compilers.Compiler
    params: Dict

    _preset_name: str   # Due to implementation this has to be stored until self.run() is called. (only then is `project` passed to us)

    def __init__(self, node, props: Dict, **kwargs):
        # Parse attributes
        self.output = untempl(node.attrib['output'], props) if 'output' in node.attrib else None

        self.compiler = compilers.find(
            name=node.attrib['compiler'] if 'compiler' in node.attrib else None, # name overrides lang if specified
            lang=node.attrib['lang']     if 'lang'     in node.attrib else None
        )

        self._preset_name = node.attrib['preset'] if 'preset' in node.attrib else None
        self.params = parse_preset(node, props)

        # Parse ingredients (subtags)
        self.objects = []
        self.linked_libs = []

    def apply_preset(self, presets: Dict):
        if self._preset_name:
            preset = project.presets[self._preset_name]
            preset = update_preset(preset, self.params)
            self.params = preset

def get_libpath(node: ET.Element, props: Dict) -> str:
    if 'libpath' in node.attrib:
        return untempl(node.attrib['libpath'], props)

class ExecutableTask(BinaryTask):
    def __init__(self, node, props: Dict, **kwargs):
        super().__init__(node, props)

        for objnode in node.iterfind('object'):
            self.objects.append(ObjectTask(objnode, props, **kwargs))

        for lnknode in node.iterfind('link'):
            self.linked_libs.append(get_libpath(lnknode, props=props))

    def run(self, project):
        self.apply_preset(project.presets)

        # Compile objects first
        for obj in self.objects:
            obj.run(project)

        log(1, 'compile {} -> {}'.format(str(flatten([o.get_files() for o in self.objects])), self.output))
        self.compiler.create_executable(untempl(self.output, project.props), flatten([obj.get_files() for obj in self.objects]), self.linked_libs, self.params)

    def __repr__(self):
        return 'compile({} -> {})'.format(str([o.output for o in self.objects]), self.output)

class SharedLibTask(BinaryTask):
    def __init__(self, node, props: Dict, **kwargs):
        super().__init__(node, props)

        for objnode in node.iterfind('object'):
            obj_task = ObjectTask(objnode, props, **kwargs)
            obj_task.for_shlib = True
            self.objects.append(obj_task)

        for lnknode in node.iterfind('link'):
            self.linked_libs.append(get_libpath(lnknode, props=props))

    def run(self, project):
        self.apply_preset(project.presets)

        # Compile objects first
        for obj in self.objects:
            obj.run(project)

        obj_files = flatten([o.get_files() for o in self.objects])
        log(1, 'compile {} -> {}'.format(str(obj_files), self.output))
        self.compiler.create_shlib(untempl(self.output, project.props), obj_files, self.linked_libs, self.params)

    def __repr__(self):
        return 'compile({} -> {})'.format(str(flatten([o.get_files() for o in self.objects])), self.output)
