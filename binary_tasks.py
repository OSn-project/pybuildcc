import xml.etree.cElementTree as ET
from typing import Dict, List
from tasks import Task
from misc import log, parse_preset, update_preset, untempl

import compilers

class ObjectTask(Task):
    source: str
    file: str

    output: str

    compiler: compilers.Compiler
    params: Dict

    _preset_name: str   # Due to implementation this has to be stored until self.run() is called. (only then is `project` passed to us)

    def __init__(self, node: ET.Element, props: Dict):
        self.source = untempl(node.attrib['source'], props) if 'source' in node.attrib else None
        self.file   = untempl(node.attrib['file'], props)   if 'file'   in node.attrib else None  # file overrides source if specified

        self.output = self.file if self.file else self.source + '.o'

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
            log(1, 'compile {} -> {}'.format(self.source, self.output))
            self.compiler.create_object(self.output, self.source, self.params)

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
            return 'compile({} -> {})'.format(self.source, self.output)

class BinaryTask(Task):
    output: str

    objects: List[ObjectTask]
    linked_libs: List[str]

    compiler: compilers.Compiler
    params: Dict

    _preset_name: str   # Due to implementation this has to be stored until self.run() is called. (only then is `project` passed to us)

    def __init__(self, node, props: Dict):
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
    def __init__(self, node, props: Dict):
        super().__init__(node, props)

        for objnode in node.iterfind('object'):
            self.objects.append(ObjectTask(objnode, props))

        for lnknode in node.iterfind('link'):
            self.linked_libs.append(get_libpath(lnknode, props=props))

    def run(self, project):
        self.apply_preset(project.presets)

        # Compile objects first
        for obj in self.objects:
            obj.run(project)

        log(1, 'compile {} -> {}'.format(str([o.output for o in self.objects]), self.output))
        self.compiler.create_executable(untempl(self.output, project.props), [obj.output for obj in self.objects], self.linked_libs, self.params)

    def __repr__(self):
        return 'compile({} -> {})'.format(str([o.output for o in self.objects]), self.output)

class SharedLibTask(BinaryTask):
    def __init__(self, node, props: Dict):
        super().__init__(node, props)

        for objnode in node.iterfind('object'):
            obj_task = ObjectTask(objnode, props)
            obj_task.for_shlib = True
            self.objects.append(obj_task)

        for lnknode in node.iterfind('link'):
            self.linked_libs.append(get_libpath(lnknode, props=props))

    def run(self, project):
        self.apply_preset(project.presets)

        # Compile objects first
        for obj in self.objects:
            obj.run(project)

        log(1, 'compile {} -> {}'.format(str([o.output for o in self.objects]), self.output))
        self.compiler.create_shlib(untempl(self.output, project.props), [obj.output for obj in self.objects], self.linked_libs, self.params)

    def __repr__(self):
        return 'compile({} -> {})'.format(str([o.output for o in self.objects]), self.output)
