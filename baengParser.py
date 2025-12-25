#!/usr/bin/env python3

import sys
import json
import re

# Creation of baengParser.py was assisted by AI.

def try_number(s):
    """Return int/float if s is a numeric literal, otherwise None.

    Parameters
    ----------
    s : str
        String that might be numeric literal

    Returns
    -------
    out : int / float / None
        Numeric contained in s as the correct type
    """
    try:
        if "." in s:
            return float(s)
        else:
            return int(s)
    except Exception:
        return None


def is_quoted(s):
    """
    Check if a string is enclosed in quotes (either single or double).

    Parameters
    ----------
    s : str
        String to check for surrounding quotes

    Returns
    -------
    out : bool
        True if the string is enclosed in matching quotes, False otherwise
    """
    s = s.strip()
    return (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'"))


def strip_quotes(s):
    """
    Remove surrounding quotes (single or double) from a string if present.

    Parameters
    ----------
    s : str
        String that may be enclosed in quotes

    Returns
    -------
    out : str
        String with surrounding quotes removed, or the original string if not quoted
    """
    s = s.strip()
    if is_quoted(s):
        return s[1:-1]
    return s


def split_args_top_level(s):
    """
    Split a string into a list of arguments, using commas as separators only at the top level.
    Ignores commas inside parentheses, allowing for nested expressions.

    Parameters
    ----------
    s : str
        String containing comma-separated arguments, possibly with nested parentheses

    Returns
    -------
    out : list[str]
        List of top-level arguments, stripped of surrounding whitespace
    """
    args = []
    cur = ""
    level = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "(":
            level += 1
            cur += ch
        elif ch == ")":
            level -= 1
            cur += ch
        elif ch == "," and level == 0:
            args.append(cur.strip())
            cur = ""
        else:
            cur += ch
        i += 1
    if cur.strip() != "":
        args.append(cur.strip())
    return args


_simple_call_re = re.compile(r'^\s*([A-Za-z_]\w*)\s*\(\s*([^\)]*)\s*\)\s*$')
"""
Regular expression to match simple function calls in a string.
This regex identifies function calls of the form `func_name(arg1, arg2, ...)`,
capturing the function name and its arguments as separate groups.

- `^\s*` matches optional leading whitespace.
- `([A-Za-z_]\w*)` captures the function name (starting with a letter or underscore, followed by alphanumeric characters).
- `\s*\(\s*` matches an opening parenthesis, allowing optional whitespace.
- `([^\)]*)` captures all characters inside the parentheses (the arguments), except closing parentheses.
- `\s*\)\s*` matches a closing parenthesis, allowing optional whitespace.
- `\s*$` matches optional trailing whitespace.

This pattern is used to parse function calls like `readSample(SAMPLEPOS - i)`
into the function name (`readSample`) and its arguments (`SAMPLEPOS - i`).
"""


def parse_atom(expr):
    """
    Parse an atomic expression into a structured format suitable for JSON representation.
    This function categorizes expressions into numeric literals, quoted strings, simple function calls,
    or complex expressions, and returns them in the appropriate format for further processing.

    - Numeric literals (e.g., `42`, `3.14`) are converted to Python `int` or `float`.
    - Quoted strings (e.g., `"hello"`, `'world'`) are stripped of their surrounding quotes.
    - Simple function calls (e.g., `readSample(SAMPLEPOS - i)`) are converted to a list format:
      `["readSample", "SAMPLEPOS - i"]`.
    - Complex expressions (e.g., `int(T_small / 3)`) are returned as raw strings.

    Parameters
    ----------
    expr : str
        The expression to parse, which may be a numeric literal, quoted string, function call, or complex expression.

    Returns
    -------
    out : int | float | str | list
        As described above
    """
    e = expr.strip()

    # numeric literal?
    num = try_number(e)
    if num is not None:
        return num

    # quoted string?
    if is_quoted(e):
        return strip_quotes(e)

    # simple function call?
    m = _simple_call_re.match(e)
    if m:
        fname = m.group(1)
        arg_text = m.group(2).strip()

        # Only parse as a list if the function is a known simple function (e.g., readSample)
        # and the argument does not contain complex expressions (e.g., operators)
        if fname in ["readSample"]:  # Add other simple functions here if necessary
            if arg_text == "":
                return [fname, []]
            parts = split_args_top_level(arg_text)
            parsed_args = []
            for p in parts:
                parsed_args.append(p.strip())
            if len(parsed_args) == 1:
                return [fname, parsed_args[0]]
            else:
                return [fname, parsed_args]

    # fallback: keep as raw string (for complex expressions or unknown functions)
    return e


def parse_arg_list(s):
    """
    Split and parse a comma-separated argument string into a list of parsed atoms.
    Uses `split_args_top_level` to split arguments and `parse_atom` to parse each argument.

    Parameters
    ----------
    s : str
        Comma-separated argument string (e.g., "arg1, arg2, func(arg3)")

    Returns
    -------
    out : list
        Parsed arguments as List (numbers, strings, or lists for function calls)
    """
    parts = split_args_top_level(s)
    return [parse_atom(p) for p in parts if p != ""]


def parse_block(lines, i=0, indent=0):
    """
    Parse a block of indented code lines into a structured list of commands.
    Recursively processes nested blocks based on indentation level.

    Parameters
    ----------
    lines : list[str]
        List of code lines to parse
    i : int, optional
        Starting line index (default: 0)
    indent : int, optional
        Current indentation level (default: 0)

    Returns
    -------
    code : list
        Parsed code block as a list of commands
    i : int
        The index of the next line to process
    """
    code = []
    n = len(lines)

    while i < n:
        raw = lines[i]

        if raw.strip() == "":
            i += 1
            continue
        cur_indent = len(raw) - len(raw.lstrip(" "))

        if cur_indent < indent:
            # end of this block
            return code, i

        line = raw.strip()

        # set IR: (fs, duration, "filename.wav")
        if line.startswith("set IR:"):
            m = re.match(r"set IR:\s*\((.*)\)\s*$", line)

            if not m:
                raise ValueError(f"Malformed IR line: {raw}")

            parts = split_args_top_level(m.group(1))
            parsed = []

            for p in parts:
                p = p.strip()
                if is_quoted(p):
                    parsed.append(strip_quotes(p))
                else:
                    num = try_number(p)
                    if num is not None:
                        parsed.append(num)
                    else:
                        # fallback to string
                        parsed.append(strip_quotes(p))

            # IR is stored at top-level in final assemble step
            code.append(("__IR__", parsed))
            i += 1
            continue

        # function definition: func name(arg1, arg2):
        if line.startswith("func "):
            m = re.match(r"func\s+([A-Za-z_]\w*)\s*\(\s*([A-Za-z0-9_,\s]*)\)\s*:\s*$", line)

            if not m:
                raise ValueError(f"Malformed func def: {raw}")

            fname = m.group(1)
            params = [p.strip() for p in m.group(2).split(",") if p.strip()]
            body, new_i = parse_block(lines, i + 1, indent + 4)

            code.append(("__FUNC__", fname, params, body))
            i = new_i
            continue

        # if / while
        if line.startswith("if ") and line.endswith(":"):
            cond = line[len("if "):-1].strip()
            body, new_i = parse_block(lines, i + 1, indent + 4)
            code.append(["if", cond, body])
            i = new_i
            continue

        if line.startswith("while ") and line.endswith(":"):
            cond = line[len("while "):-1].strip()
            body, new_i = parse_block(lines, i + 1, indent + 4)
            code.append(["while", cond, body])
            i = new_i
            continue

        # print(...)
        if line.startswith("print(") and line.endswith(")"):
            inner = line[len("print("):-1].strip()
            # keep argument as-is (preserve quotes if present)
            code.append(["print", inner])
            i += 1
            continue

        # export(...)
        if line.startswith("export(") and line.endswith(")"):
            inner = line[len("export("):-1].strip()
            # treat as string filename (strip quotes if provided)
            if is_quoted(inner):
                fname = strip_quotes(inner)
            else:
                fname = inner
            code.append(["export", fname])
            i += 1
            continue

        # setSample(...) as statement
        if line.startswith("setSample(") and line.endswith(")"):
            inner = line[len("setSample("):-1].strip()
            args = parse_arg_list(inner)
            # expected two args: pos and value
            # represent as ["setSample", arg1, arg2]
            code.append(["setSample", args[0], args[1] if len(args) > 1 else None])
            i += 1
            continue

        # readSample(...) used as expression will be handled via parse_atom

        # assignment: a = expr
        if "=" in line and not line.startswith(("if ", "while ")):
            left, right = line.split("=", 1)
            var = left.strip()
            rhs = right.strip()
            parsed_rhs = parse_atom(rhs)
            code.append(["define", var, parsed_rhs])
            i += 1
            continue

        # plain function call like reflections(5)
        mcall = _simple_call_re.match(line)
        if mcall:
            fname = mcall.group(1)
            arg_text = mcall.group(2).strip()

            if arg_text == "":
                args = []
            else:
                args = parse_arg_list(arg_text)

            code.append([fname, args])
            i += 1
            continue

        # Unknown line
        raise ValueError(f"Unrecognized line: {raw}")

    return code, i


def translate(source_text):
    """
    Parse source text into an intermediate representation, functions, and main code.
    Splits the input source into lines, parses them into structured
    blocks, and organizes the result into a dictionary.

    Parameters
    ----------
    source_text : str
        Full source code text to be translated and parsed.

    Returns
    -------
    result : dict
        Dictionary with the following structure:
        - "IR": list
            Intermediate representation block (empty list if not present).
        - "<function_name>": dict
            For each user-defined function, a dictionary with keys
            "PARAMS" (list) and "CODE" (list).
        - "CODE": list
            Main (top-level) code not belonging to IR or a function.
    """
    lines = source_text.splitlines()
    parsed, _ = parse_block(lines, 0, 0)

    result = {}
    main_code = []

    for item in parsed:

        # IR
        if isinstance(item, tuple) and item[0] == "__IR__":
            result["IR"] = item[1]
            continue

        # user function
        if isinstance(item, tuple) and item[0] == "__FUNC__":
            _, fname, params, body = item
            result[fname] = {
                "PARAMS": params,
                "CODE": body
            }
            continue

        # everything else is main code
        main_code.append(item)

    if "IR" not in result:
        result["IR"] = []

    result["CODE"] = main_code
    return result


if __name__ == "__main__":
    # check if file path is given as an argument
    if len(sys.argv) < 2:
        raise SystemExit("Missing path: <filename.baeng>")

    # fetch file path
    path = sys.argv[1]

    # check if file is .baeng
    if not path.endswith(".baeng"):
        raise SystemExit("File is not a .baeng")

    try:
        with open(path, "rt") as fh:
            content = fh.read()

        program = translate(content)

        print(json.dumps(program, indent=4))

    except FileNotFoundError:
        raise SystemExit(f"File not found: {path}")

    except Exception as e:
        raise SystemExit(f"Error: {e}")