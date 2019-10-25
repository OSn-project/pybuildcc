from typing import Dict, List
import xml.etree.cElementTree as ET
from errors import *

def parse_conditional(node: ET.Element, props: Dict) -> bool:
    if 'if' in node.attrib:
        if 'eq' in node.attrib:
            return (props[node.attrib['if']] == node.attrib['eq'])
        elif 'neq' in node.attrib:
            return (props[node.attrib['if']] != node.attrib['neq'])
        else:
            return (node.attrib['if'] in props)     # Else just evaluate existence
    else:
        return True
