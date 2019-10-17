class FileFormatError(Exception):
    def __init__(self, msg=None, file=None, tag=None):
        super().__init__(msg)
        self.file = file
        self.tag = tag

class ParseError(Exception):
    pass
