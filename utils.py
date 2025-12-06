import re

def getLegalPath(rawPath: str) -> str:

    replacedPath = rawPath

    def getFullwidth(char: str) -> str:
        if len(char) != 1: return char
        if not ord(char) in range(0x20, 0x80):
            return char
        else:
            return chr(ord(char) - 0x20 + 0xFF00)

    for m in re.finditer(r'[\\/:*?"<>|\r\n]', rawPath):
        replacedPath = replacedPath[:m.start()] + getFullwidth(m.group()) + replacedPath[m.end():]
    
    return replacedPath