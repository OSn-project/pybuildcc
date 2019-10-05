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

        if file:
            self.parse(file)

    def parse(self, file):
        root = ET.ElementTree(file=file).getroot()

        os.chdir(os.path.dirname(args.file))

        # Stuff in project is static (you can't run it)
        if 'default' in root.attrib: self.default = root.attrib['default']

        # Parse properties
        def parse_prop(node: ET.Element, props: Dict, prefix: str = ''):
            name = prefix + node.attrib['name']

            if 'value' in node.attrib:  # Some properties may just be containers and have no value
                props[name] = node.attrib['value']

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
        self.targets = dict([(node.attrib['name'], Target(node, props=self.props)) for node in root.iterfind('target')])

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

    project = Project(file=args.file)
    log(3, project.__repr__())

    try:
        tgtname = args.target if args.target else project.default
        log(1, 'Running {}target {}...'.format('' if args.target else 'default ', tgtname))
        project.run(tgtname)
    except KeyError as k:
        print('Error: No target named', k)
