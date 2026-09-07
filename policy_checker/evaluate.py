"""Tiny evaluator for the Spectra subset we emit: boolean connectives, next(), G(...), GF(...).

Used to explain a counter-strategy: which rule does each losing controller response violate?
"""
from __future__ import annotations

import re
from typing import Dict, Optional

TOK = re.compile(r"\s*(?:(->|<->|[()!&|])|([A-Za-z_][A-Za-z0-9_]*))")


class Expr:
    def __init__(self, kind, *args):
        self.kind, self.args = kind, args

    def __repr__(self):
        return f"{self.kind}{self.args}"


class Parser:
    def __init__(self, s: str):
        self.toks = []
        pos = 0
        s = s.strip()
        while pos < len(s):
            m = TOK.match(s, pos)
            if not m or m.end() == pos:
                raise ValueError(f"cannot tokenise {s[pos:pos+20]!r}")
            self.toks.append(m.group(1) or m.group(2))
            pos = m.end()
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def eat(self, t=None):
        tok = self.peek()
        if t is not None and tok != t:
            raise ValueError(f"expected {t!r}, got {tok!r}")
        self.i += 1
        return tok

    # precedence: <-> lowest, then ->, |, &, !
    def parse(self):
        e = self.iff()
        if self.peek() is not None:
            raise ValueError(f"trailing tokens {self.toks[self.i:]}")
        return e

    def iff(self):
        l = self.imp()
        while self.peek() == "<->":
            self.eat(); l = Expr("iff", l, self.imp())
        return l

    def imp(self):
        l = self.disj()
        if self.peek() == "->":
            self.eat(); return Expr("imp", l, self.imp())   # right assoc
        return l

    def disj(self):
        l = self.conj()
        while self.peek() == "|":
            self.eat(); l = Expr("or", l, self.conj())
        return l

    def conj(self):
        l = self.unary()
        while self.peek() == "&":
            self.eat(); l = Expr("and", l, self.unary())
        return l

    def unary(self):
        t = self.peek()
        if t == "!":
            self.eat(); return Expr("not", self.unary())
        if t == "(":
            self.eat(); e = self.iff(); self.eat(")"); return e
        if t in ("G", "alw", "GF", "alwEv", "next"):
            self.eat(); self.eat("("); e = self.iff(); self.eat(")")
            return Expr({"G": "G", "alw": "G", "GF": "GF", "alwEv": "GF", "next": "next"}[t], e)
        if t in ("true", "TRUE"):
            self.eat(); return Expr("const", True)
        if t in ("false", "FALSE"):
            self.eat(); return Expr("const", False)
        if t is None or not re.match(r"[A-Za-z_]", t):
            raise ValueError(f"unexpected token {t!r}")
        self.eat(); return Expr("var", t)


def parse(s: str) -> Expr:
    return Parser(s).parse()


def temporal_kind(e: Expr) -> str:
    """'initial' | 'safety' | 'justice'"""
    if e.kind == "G":
        return "safety"
    if e.kind == "GF":
        return "justice"
    return "initial"


def uses_next(e: Expr) -> bool:
    if e.kind == "next":
        return True
    return any(isinstance(a, Expr) and uses_next(a) for a in e.args)


def evaluate(e: Expr, cur: Dict[str, bool], nxt: Optional[Dict[str, bool]] = None) -> Optional[bool]:
    """Evaluate a state (or transition) formula. Strips a leading G. Returns None if a needed value is missing."""
    if e.kind == "G":
        return evaluate(e.args[0], cur, nxt)
    if e.kind == "GF":
        return None   # liveness: not decidable on one step
    if e.kind == "const":
        return e.args[0]
    if e.kind == "var":
        return cur.get(e.args[0])
    if e.kind == "next":
        if nxt is None:
            return None
        return evaluate(e.args[0], nxt, None)
    if e.kind == "not":
        v = evaluate(e.args[0], cur, nxt); return None if v is None else (not v)
    a = evaluate(e.args[0], cur, nxt); b = evaluate(e.args[1], cur, nxt)
    if e.kind == "and":
        if a is False or b is False: return False
        return None if None in (a, b) else True
    if e.kind == "or":
        if a is True or b is True: return True
        return None if None in (a, b) else False
    if e.kind == "imp":
        if a is False or b is True: return True
        return None if None in (a, b) else False
    if e.kind == "iff":
        return None if None in (a, b) else (a == b)
    raise ValueError(e.kind)
