import re
from os import system

global log_level
log_level = 1

def log(lvl, msg):
    if lvl <= log_level: print(msg)

def exec_cmd(cmd: str):
    log(2, cmd)
    system(cmd)

def untempl(text, props):
    def get_prop(match):
        return props[match.group(1)]

    return re.sub('\${([A-Za-z.-_]+)}', get_prop, text)

preset_attrs = ['debug-symbols']
def parse_preset(node, props={}):
    preset = {}

    for attr in preset_attrs:
        if attr in node.attrib:
            preset[attr] = node.attrib[attr]

    # Includes
    preset['includes'] = []
    preset['defines'] = []

    for include_tag in node.iterfind('include'):
        preset['includes'].append(untempl(include_tag.attrib['dir'], props))
    for define_tag in node.iterfind('define'):
        preset['defines'].append(untempl(define_tag.attrib['key'], props))

    return preset

def update_preset(preset, more):
    # Merge lists instead of replacing them
    includes = preset.get('includes', []) + more.get('includes', [])
    defines  = preset.get('defines', [])  + more.get('defines', [])

    preset.update(more)

    preset['includes'] = includes
    preset['defines'] = defines

    return preset
