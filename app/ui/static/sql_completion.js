const _SQL_COMPLETION_VERSION = "2.0.0";

/**
 * DuckBricks SQL Completion Engine
 *
 * Provides CodeMirror 6 autocompletion for:
 *   - DuckDB keywords and built-in functions
 *   - Catalog / schema / table identifiers (context-aware after FROM/JOIN)
 *   - Column identifiers (context-aware after SELECT/WHERE/etc., including
 *     dot-prefix resolution and alias tracking)
 *
 * Architecture:
 *   SqlContextParser  — stateless SQL text analysis
 *   SqlCompletionSource — owns schema data and implements the CM6 completion source
 *   mount(editorId)   — bootstraps the engine on a NiceGUI codemirror instance
 */

// ─── DuckDB Vocabulary ────────────────────────────────────────────────────────

const DUCKDB_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "OFFSET",
    "JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "FULL OUTER JOIN", "CROSS JOIN",
    "LATERAL JOIN", "ASOF JOIN", "ANTI JOIN", "SEMI JOIN",
    "INSERT INTO", "UPDATE", "DELETE FROM",
    "CREATE TABLE", "CREATE TABLE AS", "CREATE OR REPLACE TABLE",
    "CREATE VIEW", "CREATE OR REPLACE VIEW", "DROP TABLE", "DROP VIEW",
    "CREATE SCHEMA", "DROP SCHEMA", "ALTER TABLE",
    "WITH", "AS", "UNION", "UNION ALL", "INTERSECT", "EXCEPT",
    "DISTINCT", "ALL", "TOP", "QUALIFY",
    "AND", "OR", "NOT", "IN", "NOT IN", "EXISTS", "NOT EXISTS",
    "LIKE", "ILIKE", "BETWEEN", "IS NULL", "IS NOT NULL",
    "CASE", "WHEN", "THEN", "ELSE", "END",
    "CAST", "TRY_CAST", "OVER", "PARTITION BY",
    "ROWS BETWEEN", "RANGE BETWEEN",
    "UNBOUNDED PRECEDING", "CURRENT ROW", "UNBOUNDED FOLLOWING",
    "TRUE", "FALSE", "NULL",
    "ASC", "DESC", "NULLS FIRST", "NULLS LAST",
    "ON", "USING", "RETURNING", "EXCLUDE", "REPLACE",
    "PIVOT", "UNPIVOT", "TABLESAMPLE", "UNNEST",
    "COPY", "DESCRIBE", "SHOW", "EXPLAIN", "ANALYZE",
    "BEGIN", "COMMIT", "ROLLBACK",
    "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "HUGEINT", "UBIGINT",
    "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC",
    "VARCHAR", "TEXT", "CHAR", "BLOB",
    "BOOLEAN", "DATE", "TIME", "TIMESTAMP", "TIMESTAMPTZ", "INTERVAL",
    "UUID", "JSON", "MAP", "STRUCT", "LIST", "ARRAY",
].map(kw => ({ label: kw, type: "keyword" }));

const DUCKDB_FUNCTIONS = [
    // Aggregate
    "count", "sum", "avg", "min", "max", "first", "last", "median", "mode",
    "stddev", "stddev_pop", "variance", "var_pop", "corr",
    "approx_count_distinct", "approx_quantile",
    "string_agg", "array_agg", "list_agg", "histogram",
    "bool_and", "bool_or", "any_value", "quantile",
    // Window
    "row_number", "rank", "dense_rank", "percent_rank", "cume_dist",
    "ntile", "lag", "lead", "first_value", "last_value", "nth_value",
    // String
    "lower", "upper", "length", "substr", "substring", "trim", "ltrim", "rtrim",
    "replace", "regexp_replace", "regexp_extract", "split_part", "string_split",
    "concat", "concat_ws", "format", "printf", "starts_with", "ends_with",
    "contains", "instr", "position", "lpad", "rpad", "repeat", "reverse",
    "md5", "sha256", "base64", "from_base64",
    // Numeric
    "abs", "ceil", "floor", "round", "trunc", "sqrt", "cbrt", "exp",
    "ln", "log", "log2", "log10", "power", "mod", "pi",
    "degrees", "radians", "sin", "cos", "tan", "asin", "acos", "atan",
    "random", "sign", "greatest", "least",
    // Date / time
    "now", "current_date", "current_timestamp",
    "date_part", "extract", "date_diff", "datediff", "date_add", "date_trunc",
    "epoch", "epoch_ms", "make_date", "make_timestamp",
    "strftime", "strptime", "to_timestamp", "age",
    "year", "month", "day", "hour", "minute", "second",
    "quarter", "week", "dayofweek", "dayofyear",
    // Conditional
    "coalesce", "nullif", "if", "iff", "ifnull", "nvl", "try",
    // Type
    "typeof", "len", "strval",
    // List / array
    "list_aggregate", "list_filter", "list_transform", "list_sort",
    "list_slice", "list_contains", "list_position", "list_distinct",
    "array_length", "array_slice", "unnest", "flatten",
    // JSON
    "json_extract", "json_extract_string", "json_valid",
    "json_array", "json_object", "json_keys", "json_type", "to_json",
    // Utility
    "current_schema", "current_catalog", "version",
    "hash", "generate_series", "range",
].map(fn => ({ label: fn, type: "function", apply: fn + "(${})" }));


// ─── SQL Context Parser ───────────────────────────────────────────────────────

class SqlContextParser {
    /**
     * True when the cursor is in a position where a table identifier is expected
     * (immediately after FROM, JOIN keywords).
     */
    static isAfterTableContext(textBefore) {
        return /\b(?:FROM|JOIN|UPDATE|INTO)\s+[\w`"$.]*$/i.test(textBefore);
    }

    /**
     * True when the cursor is in a position where a column identifier is expected
     * (SELECT, WHERE, AND, OR, ON, HAVING, SET, GROUP BY, ORDER BY).
     */
    static isAfterColumnContext(textBefore) {
        return /\b(?:SELECT|WHERE|AND|OR|ON|HAVING|SET|BY)\b[^;]*$/is.test(textBefore);
    }

    /**
     * Parse all table references and their aliases from the full SQL.
     * Returns Map<lowercased_alias_or_shortname → lowercased_full_path>.
     *
     * The optional alias group uses a negative lookahead so that SQL keywords
     * (JOIN, ON, WHERE, …) are never mistaken for implicit aliases.  Without
     * this guard the greedy capture would consume the next keyword, preventing
     * subsequent FROM/JOIN clauses from being matched.
     */
    static extractTableAliases(sql) {
        const aliases = new Map();
        const RESERVED =
            "FROM|JOIN|LEFT|RIGHT|INNER|FULL|OUTER|CROSS|LATERAL|ASOF|ANTI|SEMI" +
            "|WHERE|ON|AND|OR|GROUP|ORDER|HAVING|LIMIT|OFFSET|UNION|INTERSECT|EXCEPT" +
            "|SELECT|WITH|AS|BY|SET|INTO|UPDATE|INSERT|DELETE|NOT|NULL|TRUE|FALSE";
        const re = new RegExp(
            `\\b(?:FROM|JOIN)\\s+([\\w.\`"]+)` +
            `(?:\\s+(?:AS\\s+)?(?!(${RESERVED})\\b)([\\w\`"]+))?`,
            "gi"
        );
        let m;
        while ((m = re.exec(sql)) !== null) {
            const path = m[1].replace(/[`"]/g, "").toLowerCase();
            const alias = (m[3] || m[1].split(".").pop()).replace(/[`"]/g, "").toLowerCase();
            aliases.set(alias, path);
            // Also register the bare table name as a key
            aliases.set(path.split(".").pop(), path);
        }
        return aliases;
    }

    /**
     * If the word under the cursor contains a dot (e.g. "t."), return the
     * left-hand side as a prefix. Otherwise return null.
     */
    static extractDotPrefix(wordText) {
        const dot = wordText.lastIndexOf(".");
        return dot >= 0 ? wordText.slice(0, dot) : null;
    }
}


// ─── Completion Source ────────────────────────────────────────────────────────

class SqlCompletionSource {
    /**
     * @param {Object} schema  { "qualified.path": [{name: string, type: string}] }
     */
    constructor(schema) {
        this._schema = schema;
        this._tableOptions = Object.keys(schema)
            .filter(k => k.split(".").length <= 3)
            .map(name => ({ label: name, type: "class", detail: "table" }));
    }

    complete(context) {
        const word = context.matchBefore(/[\w`"$.]+/) ?? { from: context.pos, to: context.pos, text: "" };

        const textBefore = context.state.sliceDoc(0, context.pos);
        const inTableCtx  = SqlContextParser.isAfterTableContext(textBefore);
        const inColumnCtx = SqlContextParser.isAfterColumnContext(textBefore);
        const wordIsEmpty = word.from === word.to;

        // When the word is empty (e.g. the cursor is right after a space) only
        // proceed if the user explicitly requested completion OR we are in a
        // position where we have specific context (FROM/JOIN/SELECT/WHERE/…).
        if (wordIsEmpty && !context.explicit && !inTableCtx && !inColumnCtx) return null;
        const wordText = context.state.sliceDoc(word.from, context.pos);
        const fullSql = context.state.doc.toString();
        const dotPrefix = SqlContextParser.extractDotPrefix(wordText);

        // "alias." prefix → columns for that specific table
        if (dotPrefix) {
            const aliases = SqlContextParser.extractTableAliases(fullSql);
            const resolvedPath = aliases.get(dotPrefix.toLowerCase()) ?? dotPrefix.toLowerCase();
            const cols = this._columnsFor(resolvedPath);
            if (cols.length > 0) {
                return {
                    from: word.from + dotPrefix.length + 1,
                    options: cols,
                    validFor: /^[\w`"$]*$/,
                };
            }
        }

        const options = [];

        if (inTableCtx) {
            options.push(...this._tableOptions);
        } else if (inColumnCtx) {
            const aliases = SqlContextParser.extractTableAliases(fullSql);
            // Only show columns from tables actually referenced in FROM/JOIN
            aliases.forEach(resolvedPath => {
                options.push(...this._columnsFor(resolvedPath));
            });
        }

        options.push(...DUCKDB_KEYWORDS, ...DUCKDB_FUNCTIONS);

        return options.length
            ? { from: word.from, options, validFor: /^[\w`"$.]*$/ }
            : null;
    }

    _columnsFor(tablePath) {
        const cols = this._schema[tablePath] ?? this._resolveColumns(tablePath);
        if (!cols) return [];
        return cols.map(c => ({
            label: typeof c === "string" ? c : c.name,
            type: "property",
            detail: typeof c === "object" ? c.type : undefined,
        }));
    }

    _resolveColumns(partialName) {
        const lower = partialName.toLowerCase();
        const key = Object.keys(this._schema).find(k =>
            k.toLowerCase() === lower ||
            k.toLowerCase().endsWith("." + lower)
        );
        return key ? this._schema[key] : null;
    }
}


// ─── Bootstrap ────────────────────────────────────────────────────────────────

async function _waitForEditor(editorId, maxWaitMs = 5000) {
    for (let elapsed = 0; elapsed < maxWaitMs; elapsed += 100) {
        const comp = window.getElement?.(editorId);
        if (comp?.editor) return comp;
        await new Promise(r => setTimeout(r, 100));
    }
    return null;
}

async function _fetchSchema() {
    try {
        const resp = await fetch("/api/completion/schema");
        if (resp.ok) return await resp.json();
    } catch (e) {
        console.warn("[sql_completion] Schema fetch failed:", e);
    }
    return {};
}

function _attachCompletion(comp, schema) {
    const source = new SqlCompletionSource(schema);
    const view = comp.editor;

    const wrappedSource = (ctx) => {
        const result = source.complete(ctx);
        if (result) {
            console.log("[sql_completion] complete() →", result.options.length,
                "options, from:", result.from, "pos:", ctx.pos,
                "sample:", result.options.slice(0, 3).map(o => o.label));
            // Check if tooltip appeared after a brief delay
            setTimeout(() => {
                const tooltip = view.dom.querySelector(".cm-tooltip-autocomplete");
                console.log("[sql_completion] tooltip element:", tooltip ? "EXISTS" : "NOT FOUND",
                    tooltip ? `(${tooltip.offsetWidth}x${tooltip.offsetHeight})` : "");
            }, 100);
        }
        return result;
    };

    const EditorState = view.state.constructor;
    const languageData = EditorState.languageData;
    const sampleEffect = comp.languageConfig.reconfigure([]);
    const StateEffect = sampleEffect.constructor;
    const appendConfig = StateEffect.appendConfig;

    if (!languageData || !appendConfig) {
        console.error("[sql_completion] Could not obtain CM6 classes from editor instance.");
        return;
    }

    view.dispatch({
        effects: appendConfig.of(
            languageData.of(() => [{
                autocomplete: wrappedSource,
            }]),
        ),
    });

    console.log("[sql_completion] Completion source attached. Tables:", Object.keys(schema).length);
}

export async function mount(editorId) {
    console.log("[sql_completion] v" + _SQL_COMPLETION_VERSION + " mount(" + editorId + ")");
    const comp = await _waitForEditor(editorId);
    if (!comp) {
        console.warn("[sql_completion] Editor not found for id:", editorId);
        return;
    }
    const schema = await _fetchSchema();
    _attachCompletion(comp, schema);
}

export async function refreshSchema(editorId) {
    const comp = window.getElement?.(editorId);
    if (!comp?.editor) return;
    const schema = await _fetchSchema();
    _attachCompletion(comp, schema);
}
