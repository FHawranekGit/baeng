import json
import re

# TODO: parts still AI slob but working. Check everything and edit comments.

def try_number(s):
    """Return int/float if s is a numeric literal, otherwise None."""
    try:
        if "." in s:
            return float(s)
        else:
            return int(s)
    except Exception:
        return None

def is_quoted(s):
    s = s.strip()
    return (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'"))

def strip_quotes(s):
    s = s.strip()
    if is_quoted(s):
        return s[1:-1]
    return s

def split_args_top_level(s):
    """
    Split by commas at top level (not inside parentheses).
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

def parse_atom(expr):
    """
    Convert an atomic expression into the proper JSON form:
      - numeric literals -> numbers
      - quoted strings -> unquoted strings
      - simple function calls (e.g., readSample(SAMPLEPOS - i)) -> ["fname", "arg"]
      - complex expressions (e.g., int(T_small / 3)) -> raw string
    """
    e = expr.strip()

    # numeric literal?
    num = try_number(e)
    if num is not None:
        return num

    # quoted string?
    if is_quoted(e):
        return strip_quotes(e)

    # Check if the expression is a simple function call (e.g., readSample(SAMPLEPOS - i))
    m = _simple_call_re.match(e)
    if m:
        fname = m.group(1)
        arg_text = m.group(2).strip()

        # Only parse as a list if the function is a known simple function (e.g., readSample)
        # and the argument does not contain complex expressions (e.g., operators)
        if fname in ["readSample"]:  # Add other simple functions here
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
    Parse comma-separated args from a function call line, return a list of parsed atoms.
    """
    parts = split_args_top_level(s)
    return [parse_atom(p) for p in parts if p != ""]

# -------------------------
# Main indentation-based parser
# -------------------------

def parse_block(lines, i=0, indent=0):
    """
    Parse lines starting at index i that are indented at least `indent` spaces.
    Returns (code_list, new_index).
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

        # set IR: (16000, 1, "output.wav")
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
            # IR is stored at top-level in final assemble step; keep as special marker
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
            # body already in JSON-style lists; attach under a dict per your IR layout
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

        # readSample(...) used as expression will be handled via parse_atom when used as assignment RHS

        # assignment: a = expr
        if "=" in line and not line.startswith(("if ", "while ")):
            left, right = line.split("=", 1)
            var = left.strip()
            rhs = right.strip()
            # # If rhs is a simple function call like readSample(X), convert to nested list
            # parsed_rhs = None
            # # detect simple single-function call without operators
            # if _simple_call_re.match(rhs) and not any(op in rhs for op in ["+", "-", "*", "/", "<", ">", "%", " and ", " or "]):
            #     parsed_rhs = parse_atom(rhs)
            #     # In the IR sample you provided, define uses ["define","name", ["readSample","SAMPLEPOS"]]
            #     # If parse_atom returned a nested list [fname, arg], use that; else keep as string
            # else:
            #     # numeric or quoted string?
            #     num = try_number(rhs)
            #     if num is not None:
            #         parsed_rhs = num
            #     elif is_quoted(rhs):
            #         parsed_rhs = strip_quotes(rhs)
            #     else:
            #         # keep expression as string (e.g., currentVal + 0.1)
            #         parsed_rhs = rhs
            parsed_rhs = parse_atom(rhs) # testing
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

# -------------------------
# Top-level translate function
# -------------------------

def translate(source_text):
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


# -------------------------
# Example usage
# -------------------------

if __name__ == "__main__":
    source = """ 
set IR: (16000, 1, "output.wav")

func initial_reflections(period, power):
    if SAMPLEPOS % period == 0 and SAMPLEPOS != 0:
        setSample(SAMPLEPOS, - (period / SAMPLEPOS) ** power)

    if SAMPLEPOS / 2 % period == 0 and SAMPLEPOS != 0:
        setSample(SAMPLEPOS, (period / SAMPLEPOS) ** power)

func small_reflections(period, factor):
    lastValue = readSample(SAMPLEPOS - period)
    currentValue = readSample(SAMPLEPOS)

    if SAMPLEPOS > period and lastValue != 0 and currentValue == 0:
        setSample(SAMPLEPOS, - lastValue * factor)

func moving_average(windowSize):
    sum = 0
    count = 0
    i = 0
    idxValue = 0

    while i < windowSize:
        if SAMPLEPOS - i >= 0:
            idxValue = readSample(SAMPLEPOS - i)
            sum = sum + idxValue
            count = count + 1
        i = i + 1

    average = sum / count
    setSample(SAMPLEPOS, average)

T = 800
P = 1.2
initial_reflections(T, P)
export("first_initial_reflections.wav")
print('created first_initial_reflections.wav')

T = 1234
P = 1.35
initial_reflections(T, P)
export("second_initial_reflections.wav")
print('created second_initial_reflections.wav')

N = 5
idx = 0
T_small = 128
F = 0.8

while idx < N:
    small_reflections(T_small, F)
    T_small = int(T_small / 3)
    F = F / 3
    idx = idx + 1

export("small_reflections.wav")
print('created small_reflections.wav')

W = 3
moving_average(W)
export("first_moving_average.wav")
print('created first_moving_average.wav')

W = 3
moving_average(W)
print('all done, created output.wav')
"""
    program = translate(source)
    print(json.dumps(program, indent=4))
