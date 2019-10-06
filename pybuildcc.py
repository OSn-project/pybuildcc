from abc import ABC, abstractmethod
from typing import Dict, List
import os, sys, re

import xml.etree.cElementTree as ET

from tasks import Task, TASKS
from misc import untempl, log_level, log, parse_preset, update_preset
import misc

class Project:
    name: str
    desc: str
    _file: str

    targets: Dict
    default: str   # default target
    props: Dict[str, str]
    presets: Dict[str, Dict[str, str]]

    def __init__(self, file=None):
        self.name = ''
        self.default = ''

        self.targets = {}
        self.props   = {}
        self.presets = {}

        self.init_props()

        if file:
            self.parse(file)

    def parse(self, file):
        root = ET.ElementTree(file=file).getroot()

        os.chdir(os.path.dirname(os.path.abspath(args.file)))

        # Stuff in project is static (you can't run it)
        self.name    = root.attrib.get('name',    None)
        self.desc    = root.attrib.get('description', None)
        self._file   = file
        self.default = root.attrib.get('default', None)

        self.import_body(root)

        self.props['project.name'] = self.name
        self.props['project.description'] = self.desc

    def import_body(self, root: ET.Element):
        '''
        Import the tasks, presets, and properties of an XML into the current project.
        Gives an error on name clashes.
        '''

        # Nodes are parsed by order and not by type because some
        # nodes may refer to ones that occure before them.
        for node in root:
            if node.tag == 'property':
                # Parse property
                def parse_prop(node: ET.Element, props: Dict, prefix=''):
                    name = prefix + node.attrib['name']

                    if 'value' in node.attrib:  # Some properties may just be containers and have no value
                        props[name] = untempl(node.attrib['value'], props)

                    # Nested properties
                    for child in node.iterfind('property'):
                        if child is not node:
                            parse_prop(child, props, prefix=name+'.')

                parse_prop(node, self.props)

            if node.tag == 'preset':
                # Parse preset
                def get_preset(name):
                    if name in self.presets:
                        # Return it if it already exists
                        return self.presets[name]
                    else:
                        node = root.find("preset[@name='%s']" % name)

                        if node is None:
                            raise KeyError('No preset named {}.'.format(name))

                        # If the node has a parent, get the parent values first and
                        # then overwrite them with this presets params.
                        if 'parent' in node.attrib:
                            params = get_preset(node.attrib['parent']).copy()
                            params = update_preset(params, parse_preset(node, self.props))
                        else:
                            params = parse_preset(node, self.props)

                        return params

                preset = get_preset(node.attrib['name'])
                self.presets[node.attrib['name']] = preset

            if node.tag == 'target':
                # Parse target
                self.targets[node.attrib['name']] = Target(node, props=self.props)

            if node.tag == 'import':
                imported = ET.ElementTree(file=node.attrib['file']).getroot()
                if imported.tag == 'buildcc':
                    self.import_body(imported)
                else:
                    raise Exception('Not a BuildCC file: ' + imported._file)

    def init_props(self):
        import getpass
        self.props['user.home'] = os.path.expanduser('~')
        self.props['user.name'] = getpass.getuser()

    def run(self, name):
        target = self.targets[name]

        for task in target.tasks:
            task.run(self)

    def __repr__(self):
        s = ''
        s += ('name:\t{}\n'.format(self.name))
        s += ('default:\t{}\n'.format(self.default))
        s += ('targets:\t{}\n'.format(list(self.targets.keys())))
        s += 'presets:\n' +    ''.join(['\t{}\t= {}\n'.format(k, v) for k, v in self.presets.items()])
        s += 'properties:\n' + ''.join(['\t{}\t= {}\n'.format(k, v) for k, v in self.props.items()])
        return s

class Target:
    tasks: List[Task]
    def __init__(self, node, props: Dict):
        self.tasks = []

        for tasknode in node:
            task = TASKS[tasknode.tag](tasknode, props)    # Look up the constructor for the given tag and call it
            self.tasks.append(task)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-target')
    parser.add_argument('-file', help="specify build file", default='build.xml')
    parser.add_argument('-v', help="verbosity: {0|1|2}", default='1')
    args = parser.parse_args()

    # import pdb;pdb.set_trace()
    misc.log_level = int(args.v)

    project = Project()

    # Load config files
    path_elems = os.path.dirname(os.path.abspath(args.file[1:])).split('/')
    for dir in ['/' + '/'.join(path_elems[:depth]) for depth in range(len(path_elems))]:
        config_file = dir + '/config.xml'
        if os.path.isfile(config_file):
            try:
                config_xml = ET.ElementTree(file=config_file).getroot()
                if config_xml.tag == 'buildcc':
                    log(3, "Loading config file `%s`" % config_file)
                    project.import_body(config_xml)
                    continue
            except:
                pass
            log(1, "info: Config file `%s` is not a BuildCC file; ignoring." % config_file)

    project.parse(args.file)

    log(3, project.__repr__())

    try:
        tgtname = args.target if args.target else project.default
        log(1, 'Running {}target `{}`...'.format('' if args.target else 'default ', tgtname))
        project.run(tgtname)
    except KeyError as k:
        print('Error: No target named', k)
