from typing import Dict, List
from abc import ABC, abstractmethod
import xml.etree.cElementTree as ET
from misc import untempl, log_level, log
import os

class Task(ABC):
    def __init__(self, node: ET.Element, props: Dict, **kwargs):
        pass

    def run(self, project):
        pass

# Core tasks

class EchoTask(Task):
    text: str
    def __init__(self, node, props: Dict, **kwargs):
        self.text = untempl(node.text, props) if node.text else ''
    def run(self, project):
        log(0, untempl(self.text, project.props))
    def __repr__(self):
        return 'echo("%s")' % self.text

class ExecTask(Task):
    text: str
    def __init__(self, node, props: Dict, **kwargs):
        self.text = untempl(node.text, props) if node.text else ''
    def run(self, project):
        log(2, self.text)
        os.system(self.text)
    def __repr__(self):
        return 'exec("%s")' % self.text

from binary_tasks import ObjectTask, ExecutableTask, SharedLibTask

TASKS = {
    'echo': EchoTask,
    'object': ObjectTask,
    'executable': ExecutableTask,
    'shared-library': SharedLibTask,
    'exec': ExecTask,
}
