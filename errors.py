class ParseError(Exception):
    def __init__(self, msg, file=None, line=None):
        self.msg  = msg
        self.file = file
        self.line = line

class PlatformError(Exception):     # An incompatibility with the compiler's target platform
    def __init__(self, msg, compiler=None):
        self.msg = msg
