r"""MASTER-RADAR directive §C2 — hand-written, line-aware tokenizer for RSL-1.

The lexer is deliberately restrictive: only an explicit allow-list of ASCII
characters may appear in strategy source. Anything else (unicode identifiers,
control characters such as NUL, backslashes, brackets, braces, semicolons,
``@``, ``&``, ``|`` ...) is rejected with :class:`DSLLexError` *before* any
parsing happens — this is the first layer of the sandbox-escape resistance.

Decisions locked here (documented behaviour):
- Numbers are plain decimals only: ``[0-9]+(\.[0-9]+)?``. No scientific
  notation (``1e9`` lexes as NUMBER ``1`` followed by IDENT ``e9`` and the
  parser then rejects the stray identifier), no leading/trailing dot, and a
  second decimal point inside one literal is a lex error.
- String literals exist ONLY for ``sym("IDENTIFIER")``. The characters inside
  a string are restricted to ``[A-Za-z0-9_.\\-]`` so path-traversal payloads
  (``/``, ``\\``) cannot even be tokenized; there are no escape sequences.
- Keywords are case-insensitive and identifiers are lowercased.
- ``#`` starts a comment that runs to end of line; the newline itself is still
  emitted because it terminates statements.
"""
from __future__ import annotations

from dataclasses import dataclass

from .errors import DSLLexError

_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGITS = "0123456789"
_IDENT_START = frozenset(_LETTERS + "_")
_IDENT_CHARS = frozenset(_LETTERS + _DIGITS + "_")
_SYM_STRING_CHARS = frozenset(_LETTERS + _DIGITS + "_.-")

# Canonical (upper-case) keyword values emitted for case-insensitive matches.
KEYWORDS: dict[str, str] = {
    "input": "INPUT",
    "risk": "RISK",
    "entry": "ENTRY",
    "exit": "EXIT",
    "alert": "ALERT",
    "and": "AND",
    "or": "OR",
    "not": "NOT",
    "sym": "SYM",
}

_ALLOWED_CHARS = _IDENT_CHARS | set("().,<>=!+-*/ \t\"#")

# Defensive cap on a single number literal; keeps absurd multi-thousand-digit
# literals from being converted into bignums. (100k-digit sources are already
# rejected earlier by the source-length budget in compile_source.)
_MAX_NUMBER_CHARS = 64

_MAX_STRING_CHARS = 24


@dataclass(frozen=True)
class Token:
    """A lexical token with a 1-based source position."""

    kind: str
    value: str | int | float | None
    line: int
    col: int


def _err(code: str, message: str, line: int, col: int) -> DSLLexError:
    return DSLLexError(message, line=line, col=col, code=code)


def tokenize(source: str) -> list[Token]:
    """Tokenize RSL-1 source into a list of tokens ending with an EOF token."""
    if not isinstance(source, str):
        raise _err("LEX_BAD_SOURCE", "strategy source must be a string", 1, 1)

    tokens: list[Token] = []
    i = 0
    n = len(source)
    line = 1
    col = 1

    while i < n:
        c = source[i]

        if c == "\n":
            tokens.append(Token("NEWLINE", None, line, col))
            i += 1
            line += 1
            col = 1
            continue
        if c == "\r":
            # accept CRLF (and lone CR) as a line terminator
            i += 1
            if i < n and source[i] == "\n":
                i += 1
            tokens.append(Token("NEWLINE", None, line, col))
            line += 1
            col = 1
            continue
        if c in " \t":
            i += 1
            col += 1
            continue
        if c == "#":
            while i < n and source[i] != "\n":
                i += 1
            continue

        if c not in _ALLOWED_CHARS:
            raise _err(
                "LEX_ILLEGAL_CHAR",
                f"illegal character {c!r} (U+{ord(c):04X}); RSL-1 allows only "
                "letters, digits, underscore, . , ( ) < > = ! + - * / space, "
                "tab, double quote and #",
                line,
                col,
            )

        if c in _DIGITS:
            start = i
            tok_col = col
            while i < n and source[i] in _DIGITS:
                i += 1
            is_float = False
            if i < n and source[i] == ".":
                if i + 1 < n and source[i + 1] in _DIGITS:
                    is_float = True
                    i += 1
                    while i < n and source[i] in _DIGITS:
                        i += 1
                    if i < n and source[i] == ".":
                        raise _err(
                            "LEX_MALFORMED_NUMBER",
                            f"number literal {source[start:i + 1]!r} has more "
                            "than one decimal point",
                            line,
                            tok_col,
                        )
                else:
                    raise _err(
                        "LEX_MALFORMED_NUMBER",
                        "number literal has a trailing '.' without digits",
                        line,
                        tok_col,
                    )
            text = source[start:i]
            if len(text) > _MAX_NUMBER_CHARS:
                raise _err(
                    "LEX_MALFORMED_NUMBER",
                    f"number literal longer than {_MAX_NUMBER_CHARS} characters",
                    line,
                    tok_col,
                )
            value: int | float = float(text) if is_float else int(text)
            tokens.append(Token("NUMBER", value, line, tok_col))
            col += i - start
            continue

        if c == '"':
            tok_col = col
            i += 1
            col += 1
            start = i
            while i < n and source[i] != '"' and source[i] != "\n":
                ch = source[i]
                if ch not in _SYM_STRING_CHARS:
                    raise _err(
                        "LEX_BAD_STRING",
                        f"invalid character {ch!r} inside string literal; "
                        'sym("...") strings allow only A-Z a-z 0-9 _ . -',
                        line,
                        col,
                    )
                i += 1
                col += 1
            if i >= n or source[i] != '"':
                raise _err(
                    "LEX_UNTERMINATED_STRING",
                    "unterminated string literal",
                    line,
                    tok_col,
                )
            text = source[start:i]
            if len(text) > _MAX_STRING_CHARS:
                raise _err(
                    "LEX_BAD_STRING",
                    f"string literal longer than {_MAX_STRING_CHARS} characters",
                    line,
                    tok_col,
                )
            tokens.append(Token("STRING", text, line, tok_col))
            i += 1
            col += 1
            continue

        if c in _IDENT_START:
            start = i
            tok_col = col
            while i < n and source[i] in _IDENT_CHARS:
                i += 1
            word = source[start:i].lower()
            if word in KEYWORDS:
                tokens.append(Token("KEYWORD", KEYWORDS[word], line, tok_col))
            else:
                tokens.append(Token("IDENT", word, line, tok_col))
            col += i - start
            continue

        two = source[i : i + 2]
        if two in (">=", "<=", "==", "!="):
            kind = {">=": "GE", "<=": "LE", "==": "EQEQ", "!=": "NE"}[two]
            tokens.append(Token(kind, None, line, col))
            i += 2
            col += 2
            continue

        single = {
            "(": "LPAREN",
            ")": "RPAREN",
            ",": "COMMA",
            ".": "DOT",
            "=": "EQ",
            ">": "GT",
            "<": "LT",
            "+": "PLUS",
            "-": "MINUS",
            "*": "STAR",
            "/": "SLASH",
        }
        if c in single:
            tokens.append(Token(single[c], None, line, col))
            i += 1
            col += 1
            continue

        raise _err(
            "LEX_BAD_OPERATOR",
            f"unexpected character {c!r}; '!' must be followed by '=' ",
            line,
            col,
        )

    tokens.append(Token("EOF", None, line, col))
    return tokens
