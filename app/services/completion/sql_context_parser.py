"""Python mirror of the browser-side SqlContextParser for testing and future server-side use."""

import re


class SqlContextParser:
    """Stateless SQL text analysis for completion context detection.

    All methods accept raw SQL text and return context signals used by
    the completion engine to decide what category of identifier to suggest.

    This class is a faithful Python port of the JavaScript SqlContextParser in
    app/ui/static/sql_completion.js — both must be kept in sync.
    """

    @staticmethod
    def is_after_table_context(text_before: str) -> bool:
        """Return True when the cursor is in a position expecting a table identifier.

        Triggered after FROM, JOIN, UPDATE, or INTO keywords.
        """
        return bool(
            re.search(
                r'\b(?:FROM|JOIN|UPDATE|INTO)\s+[\w`"$.]*$',
                text_before,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def is_after_column_context(text_before: str) -> bool:
        """Return True when the cursor is in a position expecting a column identifier.

        Triggered after SELECT, WHERE, AND, OR, ON, HAVING, SET, or BY keywords,
        up to the most recent semicolon.
        """
        return bool(
            re.search(
                r"\b(?:SELECT|WHERE|AND|OR|ON|HAVING|SET|BY)\b[^;]*$",
                text_before,
                re.IGNORECASE | re.DOTALL,
            )
        )

    # SQL keywords that the alias capture group must never match.
    _RESERVED_ALIAS_WORDS: frozenset[str] = frozenset(
        {
            "from",
            "join",
            "left",
            "right",
            "inner",
            "full",
            "outer",
            "cross",
            "lateral",
            "asof",
            "anti",
            "semi",
            "where",
            "on",
            "and",
            "or",
            "group",
            "order",
            "having",
            "limit",
            "offset",
            "union",
            "intersect",
            "except",
            "select",
            "with",
            "as",
            "by",
            "set",
            "into",
            "update",
            "insert",
            "delete",
            "not",
            "null",
            "true",
            "false",
        }
    )

    # Negative lookahead that prevents SQL keywords from being captured as aliases.
    # Keeping it as a constant makes the compiled pattern easier to read and avoids
    # repeating the long keyword list.
    _RESERVED_LOOKAHEAD: str = (
        r"(?!(?:FROM|JOIN|LEFT|RIGHT|INNER|FULL|OUTER|CROSS|LATERAL|ASOF|ANTI|SEMI"
        r"|WHERE|ON|AND|OR|GROUP|ORDER|HAVING|LIMIT|OFFSET|UNION|INTERSECT|EXCEPT"
        r"|SELECT|WITH|AS|BY|SET|INTO|UPDATE|INSERT|DELETE)\b)"
    )

    @classmethod
    def extract_table_aliases(cls, sql: str) -> dict[str, str]:
        """Parse all FROM/JOIN table references and their aliases from the full SQL.

        Returns a dict mapping every resolvable alias (or bare table name) to
        its fully-qualified path, both lowercased.

        The optional alias capture group uses a negative lookahead so that SQL
        keywords (JOIN, ON, WHERE, …) are never mistaken for implicit aliases.
        Without this guard the greedy capture would swallow the next keyword,
        preventing subsequent FROM/JOIN clauses from being discovered.

        Examples:
            "FROM users AS u"  →  {"u": "users", "users": "users"}
            "FROM main.orders" →  {"orders": "main.orders"}
        """
        aliases: dict[str, str] = {}
        pattern = re.compile(
            r'\b(?:FROM|JOIN)\s+([\w.`"]+)'
            r"(?:\s+(?:AS\s+)?" + cls._RESERVED_LOOKAHEAD + r'([\w`"]+))?',
            re.IGNORECASE,
        )
        for match in pattern.finditer(sql):
            path = re.sub(r'[`"]', "", match.group(1)).lower()
            alias_raw = match.group(2) if match.group(2) else match.group(1).split(".")[-1]
            alias = re.sub(r'[`"]', "", alias_raw).lower()
            aliases[alias] = path
            aliases[path.split(".")[-1]] = path
        return aliases

    @staticmethod
    def extract_dot_prefix(word_text: str) -> str | None:
        """Return the substring before the last dot, or None when no dot is present.

        Used to resolve "alias.col" or "schema.table" dot-notation prefixes.

        Examples:
            "t.col"              → "t"
            "schema.table"       → "schema"
            "catalog.schema.tbl" → "catalog.schema"
            "users"              → None
        """
        dot_index = word_text.rfind(".")
        return word_text[:dot_index] if dot_index >= 0 else None
