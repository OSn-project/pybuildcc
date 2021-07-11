#!/usr/bin/env python3

from abc import ABC, abstractmethod
from typing import Dict, List
import os, sys, re

import xml.etree.cElementTree as ET

from tasks import Task, TASKS
from filegens import FileGenTask, FileSet
from misc import untempl, log_level, log, parse_preset, update_preset, ExecCommandError
import misc
from errors import ParseError
from conditional import parse_conditional

class Project:
    name: str = ''
    default: str = ''   # default target

    targets: Dict
    props: Dict[str, str]
    presets: Dict[str, Dict[str, str]]
    filesets: Dict[str, FileSet]

    def __init__(self, file=None):
        self.name = ''
        self.default = ''

        self.targets  = {}
        self.props    = {}
        self.presets  = {}
        self.filesets = {}

        self.init_props()

        if file:
            self.parse(file)

    def parse(self, file):
        os.chdir(os.path.dirname(os.path.abspath(file)))

        self.set__file(file)    # Initialize _file.* properties

        root = ET.ElementTree(file=file).getroot()
        self.import_xml(root, file=file)

        self.name    = root.attrib.get('name',    None)
        self.default = root.attrib.get('default', None)

    def import_xml(self, root: ET.Element, file=''):
        if root.tag != 'buildcc':
            raise ParseError(f'file `{file}` is not a buildcc file. (root tag is `{root.tag}`)')

        parse_args = {"props": self.props, "filesets": self.filesets}

        # Parse imports
        for node in root.iterfind('import'):
            file = untempl(node.attrib['file'], self.props)
            log(3, 'Importing `{}`.'.format(file))
            self.import_file(file)

        # Parse properties
        def parse_prop(node: ET.Element, props: Dict, prefix: str = ''):
            if not parse_conditional(node, props): return

            name = prefix + node.attrib['name']

            if 'value' in node.attrib and name not in props:  # Some properties may just be containers and have no value
                props[name] = untempl(node.attrib['value'], props)

            # Nested properties
            for child in node.iterfind('property'):
                if child is not node:
                    parse_prop(child, props, prefix=name+'.')

        for node in root.iterfind('property'):
            parse_prop(node, self.props)

        # Parse presets
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

        for node in root.iterfind('preset'):
            preset = get_preset(node.attrib['name'])
            self.presets[node.attrib['name']] = preset

        # Parse filesets

        for node in root.iterfind('fileset'):
            self.filesets[node.attrib['name']] = FileSet(node, **parse_args)

        # Parse targets
        for node in root.iterfind('target'):
            try:
                self.targets[node.attrib['name']] = Target(node, **parse_args)
            except KeyError:
                raise ParseError('Element missing `name` attribute.')

    def import_file(self, path: str):
        old_file = self.props.get('_file.path', '')     # Retain old file path so that we can go back to it again after we've imported this
        self.set__file(path)

        root = ET.ElementTree(file=path).getroot()
        self.import_xml(root, file=path)

        self.set__file(old_file)

    def init_props(self):
        import getpass
        self.props['user.home'] = os.path.expanduser('~')
        self.props['user.name'] = getpass.getuser()

    def set__file(self, path: str):
        path = os.path.abspath(path)
        self.props['_file.path'] = path
        self.props['_file.dir']  = os.path.dirname(path)
        self.props['_file.name'] = os.path.basename(path)

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
        s += 'filesets:\n' +   ''.join(['\t{}\t= [\n\t\t{}\n\t]\n'.format(k, ',\n\t\t'.join(fileset.get_files())) for k, fileset in self.filesets.items()])
        return s

class Target:
    tasks: List[Task]
    def __init__(self, node, props: Dict, **kwargs):
        self.tasks = []

        for tasknode in node:
            task = TASKS[tasknode.tag](tasknode, props=props, **kwargs)    # Look up the constructor for the given tag and call it
            self.tasks.append(task)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-objtags', metavar='DIR', default=None, help="Prints an object tag for every C and C++ file in the specified directory, then aborts.")
    parser.add_argument('-target')
    parser.add_argument('-file', help="Specify build file", default='build.xml')
    parser.add_argument('-v', help="Verbosity: [0-3] (default=1)", default='1')
    parser.add_argument('-p', help="Set a property. Overrides properties from files. [name=value]", action='append', default=[])
    args = parser.parse_args()

    if args.objtags:
        objtags_for(args.objtags)
        return

    # import pdb;pdb.set_trace()
    misc.log_level = int(args.v)

    project = Project()

    # Command line properties
    for propstr in args.p:
        if re.match("^[a-zA-Z1-9\.\-]+\=[^=]+$", propstr):
            name, val = propstr.split('=')
            project.props[name] = val
        elif re.match("^[a-zA-Z1-9\.\-]+$", propstr):
            project.props[propstr] = ''
        else:
            raise Exception("Invalid property argument `-p {}`".format(propstr))

    # Go up our path, importing any config files above us
    path_bits = os.path.abspath('.').split('/')[1:]
    for dir in ['/' + '/'.join(path_bits[:i]) for i in range(len(path_bits))]:
        file = dir + '/config.xml'
        if os.path.isfile(file):
            try:
                log(3, 'Importing config file `{}`.'.format(file))
                project.import_file(file)
            except FileFormatError:
                log(1, 'Config file `{}` is not a BuildCC file, ignoring.'.format(file))

    # Parse the build file
    if args.file:
        build_file = args.file
    elif os.path.isfile('build.xml'):
        build_file = os.path.abspath(args.file)
    else:
        log(1, 'No build file specified or found.')
        return

    try:
        project.parse(build_file)
    except ParseError as err:
        print('Error: ' + err.msg)
        return

    log(3, project.__repr__())

    try:
        tgtname = args.target if args.target else project.default
        log(1, f'Running {"" if args.target else "default "}target `{tgtname}`...')
        project.run(tgtname)
    except ExecCommandError as err:
        print(f'Error: The following command exited with code {err.code}:\n\n{err.cmd}')
    except KeyError as k:
        print('Error: No target named', k)

def objtags_for(dir_path):
    obj_tag = '<object lang="{}" source="{}" />'
    if not dir_path.endswith('/'): dir_path += '/'

    for file in [dir_path + ent for ent in os.listdir(dir_path) if os.path.isfile(dir_path + ent)]:
        if file.lower().endswith('.c'):
            print(obj_tag.format('c', file))

        if (file.lower().endswith('.cc') or
            file.lower().endswith('.cpp') or
            file.lower().endswith('.c++')):
            print(obj_tag.format('cpp', file))

if __name__ == "__main__":
    main()
