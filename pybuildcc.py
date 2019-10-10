#!/usr/bin/env python3

from abc import ABC, abstractmethod
from typing import Dict, List
import os, sys, re

import xml.etree.cElementTree as ET

from tasks import Task, TASKS
from misc import untempl, log_level, log, parse_preset, update_preset
import misc

class Project:
    name: str = ''
    default: str = ''   # default target

    targets: Dict
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

        os.chdir(os.path.dirname(os.path.abspath(file)))

        # Stuff in project is static (you can't run it)
        self.name    = root.attrib.get('name',    None)
        self.default = root.attrib.get('default', None)

        # Parse properties
        def parse_prop(node: ET.Element, props: Dict, prefix: str = ''):
            name = prefix + node.attrib['name']

            if 'value' in node.attrib:  # Some properties may just be containers and have no value
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

        # Parse targets
        for node in root.iterfind('target'):
            try:
                self.targets[node.attrib['name']] = Target(node, props=self.props)
            except KeyError:
                raise Exception('Element missing `name` attribute.')

    def init_props(self):
        import getpass
        self.props['user.home'] = os.path.expanduser('~')
        self.props['user.'] = os.path.expanduser('~')

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

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-objtags', metavar='DIR', default=None, help="Prints an object tag for every C and C++ file in the specified directory, then aborts.")
    parser.add_argument('-target')
    parser.add_argument('-file', help="specify build file", default='build.xml')
    parser.add_argument('-v', help="verbosity: {0|1|2}", default='1')
    args = parser.parse_args()

    if args.objtags:
        objtags_for(args.objtags)
        return

    # import pdb;pdb.set_trace()
    misc.log_level = int(args.v)

    project = Project(file=args.file)
    log(3, project.__repr__())

    try:
        tgtname = args.target if args.target else project.default
        log(1, 'Running {}target `{}`...'.format('' if args.target else 'default ', tgtname))
        project.run(tgtname)
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

if __name__ == "__main__": main()
