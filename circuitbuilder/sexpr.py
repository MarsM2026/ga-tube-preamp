"""Minimale S-expressie-lezer/schrijver voor KiCad-bestanden.

Een lijst wordt een Python-list; atomen blijven strings. Strings tussen
aanhalingstekens worden als `Q("...")` bewaard zodat ze bij het schrijven weer
gequote worden.
"""

from __future__ import annotations


class Q(str):
    """Een gequote string."""


def parse(text: str):
    tokens = _tokenize(text)
    pos = 0

    def read():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        if tok == "(":
            lst = []
            while tokens[pos] != ")":
                lst.append(read())
            pos += 1
            return lst
        return tok

    return read()


def _tokenize(text: str) -> list:
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c in "()":
            out.append(c)
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while text[j] != '"':
                if text[j] == "\\":
                    buf.append(text[j:j + 2])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            out.append(Q("".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            out.append(text[i:j])
            i = j
    return out


def dump(node, indent: int = 0) -> str:
    if isinstance(node, Q):
        return '"' + str(node) + '"'
    if not isinstance(node, list):
        return str(node)
    if not node:
        return "()"
    simple = all(not isinstance(x, list) for x in node)
    if simple:
        return "(" + " ".join(dump(x) for x in node) + ")"
    pad = "\t" * (indent + 1)
    parts = [dump(node[0])]
    for x in node[1:]:
        if isinstance(x, list):
            parts.append("\n" + pad + dump(x, indent + 1))
        else:
            parts.append(" " + dump(x))
    return "(" + "".join(parts) + "\n" + "\t" * indent + ")"


def find(node, key):
    """Eerste sub-lijst met kop `key`."""
    for x in node:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def find_all(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]
