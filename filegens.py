from typing import Dict, List
from abc import ABC, abstractmethod
import xml.etree.cElementTree as ET
from misc import untempl, flatten, log_level, log
import os, itertools, glob

from tasks import Task

class FileGen(Task):
    ''' Any task which generates a file and can be nested '''

    def __init__(self, node: ET.Element, props: Dict, **kwargs):
        pass

    # @abstractmethod
    def get_filetype(self) -> str:
        # pass
        return ''

    @abstractmethod
    def get_files(self) -> List[str]:
        ''' For tasks, this should already be known before .run() is called. '''
        pass

# Core sources

class SingleFileSource(FileGen):
    def __init__(self, node: ET.Element, props: Dict, **kwargs):
        self.path = os.path.abspath(
            untempl(node.attrib['path'], props)
        )

    def get_files(self):
        return [self.path]

class WildcardFileSource(FileGen):
    def __init__(self, node: ET.Element, props: Dict, **kwargs):
        self.pattern = os.path.abspath(
            untempl(node.attrib['pattern'], props)
        )

    def get_files(self):
        return [os.path.abspath(path) for path in glob.glob(self.pattern, recursive=False)]

class FileSet(FileGen):
    sources: List

    def __init__(self, node: ET.Element, props: Dict, **kwargs):
        self.sources = []

        for source_node in node.iterfind('file'):
            self.sources.append(SingleFileSource(source_node, props))

        for source_node in node.iterfind('wildcard'):
            self.sources.append(WildcardFileSource(source_node, props))

    def get_files(self):
        return flatten(
            [source.get_files() for source in self.sources]
        )
