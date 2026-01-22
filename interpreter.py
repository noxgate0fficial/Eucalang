import math
import re

class LangError(Exception):
    pass

class Interpreter:
    def __init__(self, source, inputs=None):
        self.raw = source.splitlines()
        self.lines = self._preprocess(self.raw)
        self.vars = {}
        self.consts = set()
        self.lists = {}
        self.procedures = {}

        self.defining_proc = False
        self.current_proc = None
        self.proc_buffer = []

        self.pc = 0
        self.loop_stack = []

        self.inputs = inputs or {} # virtual console inputs

    # ---------------- PREPROCESS ----------------
    def _preprocess(self, lines):
        out = []
        in_comment = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("//"):
                in_comment = True
                continue
            if line.startswith("\\\\"):
                in_comment = False
                continue
            if in_comment or line.startswith("#"):
                continue
            out.append(line)
        return out

    # ---------------- RUN ----------------
    def run(self):
        if not self.lines[0].startswith("When container main"):
            raise LangError("Program must start with When container main(int):")
        self.pc = 1
        while self.pc < len(self.lines):
            line = self.lines[self.pc]
            if line == "End;" and not self.defining_proc:
                break
            self.exec_line(line)
            self.pc += 1

    # ---------------- EXECUTE LINE ----------------
    def exec_line(self, line):
        if line.startswith("def procedure"):
            if not line.endswith(":"):
                raise LangError("Procedure definition must end with ':'")
            name = line.split()[2].replace(":", "")
            self.defining_proc = True
            self.current_proc = name
            self.proc_buffer = []
            return

        if self.defining_proc:
            if line == "End;":
                self.procedures[self.current_proc] = self.proc_buffer.copy()
                self.defining_proc = False
                self.current_proc = None
                self.proc_buffer = []
            else:
                self.proc_buffer.append(line)
            return

        if line.startswith("call "):
            name = line.split()[1].replace(";", "")
            if name not in self.procedures:
                raise LangError(f"Procedure '{name}' not defined")
            for proc_line in self.procedures[name]:
                self.exec_line(proc_line)
            return

        if line.startswith("def "):
            self.def_var(line)
        elif line.startswith("console.type"):
            self.console(line)
        elif line.startswith("if "):
            self.if_block(line)
        elif line.startswith("else:"):
            self.skip_block()
        elif line.startswith("while "):
            self.while_block(line)
        elif line.startswith("create list"):
            self.create_list(line)
        elif line.startswith("append"):
            self.append_list(line)
        elif line.startswith("remove"):
            self.remove_list(line)
        elif line.startswith("List ") and " length()" in line:
            self.list_length(line)
        elif line.startswith("filter"):
            self.filter_list(line)
        elif line == "break;":
            self.break_loop()
        elif line == "skip;":
            self.skip_loop()
        elif line.startswith("return"):
            pass
        else:
            raise LangError(f"Unknown statement: {line}")

    # ---------------- VARIABLES ----------------
    def def_var(self, line):
        m = re.match(r"def (var|const) (\w+) = (.+);", line)
        if not m:
            raise LangError("Invalid variable definition")
        kind, name, expr = m.groups()
        expr = expr.strip()

        # Virtual console input
        if expr.startswith("input from"):
            m_input = re.match(r'input from "(.*)"', expr)
            if not m_input:
                raise LangError("Invalid input syntax")
            prompt = m_input.group(1)
            val = self.inputs.get(prompt, "")
        else:
            val = self.eval_expr(expr)

        self.vars[name] = val
        if kind == "const":
            self.consts.add(name)

    # ---------------- EXPRESSIONS ----------------
    def eval_expr(self, expr):
        expr = expr.strip()
        if '+' in expr:
            parts = expr.split('+')
            return ''.join(str(self.eval_expr(p.strip())) for p in parts)
        if expr.isdigit():
            return int(expr)
        if expr.replace('.', '', 1).isdigit():
            return float(expr)
        if expr in self.vars:
            return self.vars[expr]
        if expr.startswith('"') and expr.endswith('"'):
            return expr[1:-1]
        if expr.startswith("sqrt("):
            return math.sqrt(self.eval_expr(expr[5:-1]))
        if expr.startswith("cbrt("):
            return self.eval_expr(expr[5:-1]) ** (1/3)
        if expr.startswith("round("):
            return round(self.eval_expr(expr[6:-1]))
        if expr.startswith("floor("):
            return math.floor(self.eval_expr(expr[6:-1]))
        if expr.startswith("ceiling("):
            return math.ceil(self.eval_expr(expr[8:-1]))
        for op in ["**", "*", "/", "-"]:
            if op in expr:
                a, b = map(str.strip, expr.split(op, 1))
                a, b = self.eval_expr(a), self.eval_expr(b)
                return {
                    "-": a - b,
                    "*": a * b,
                    "/": a / b,
                    "**": a ** b
                }[op]
        raise LangError(f"Invalid expression: {expr}")

    # ---------------- CONDITIONS ----------------
    def eval_cond(self, cond, element=None):
        if element is not None:
            cond = cond.replace("$$", str(element))
        for op in ["==", "!=", ">=", "<=", ">", "<"]:
            if op in cond:
                a, b = map(str.strip, cond.split(op))
                a, b = self.eval_expr(a), self.eval_expr(b)
                return {
                    "==": a == b,
                    "!=": a != b,
                    ">": a > b,
                    "<": a < b,
                    ">=": a >= b,
                    "<=": a <= b
                }[op]
        if cond.startswith("not "):
            return not self.eval_cond(cond[4:], element)
        return bool(self.eval_expr(cond))

    # ---------------- CONTROL FLOW ----------------
    def if_block(self, line):
        cond = line[3:-1].strip()
        result = self.eval_cond(cond)
        self.pc += 1
        if result:
            while self.lines[self.pc] != "End;":
                self.exec_line(self.lines[self.pc])
                self.pc += 1
        else:
            self.skip_block()

    def while_block(self, line):
        cond = line[6:-1].strip()
        start = self.pc
        self.loop_stack.append(start)
        self.pc += 1
        while self.eval_cond(cond):
            self.pc = start + 1
            while self.lines[self.pc] != "End;":
                self.exec_line(self.lines[self.pc])
                self.pc += 1
        self.loop_stack.pop()
        self.skip_block()

    def skip_block(self):
        depth = 1
        while depth:
            self.pc += 1
            if self.lines[self.pc].endswith(":"):
                depth += 1
            if self.lines[self.pc] == "End;":
                depth -= 1

    def break_loop(self):
        self.skip_block()

    def skip_loop(self):
        self.skip_block()

    # ---------------- I/O ----------------
    def console(self, line):
        m = re.match(r'console\.type\((.*)\);', line)
        if not m:
            raise LangError("Invalid console.type")
        print(self.eval_expr(m.group(1)))

    # ---------------- LISTS ----------------
    def create_list(self, line):
        name = re.match(r'create list\("(.*)"\);', line).group(1)
        self.lists[name] = []

    def append_list(self, line):
        name, value = re.match(r'append\("(.*)", (.*)\);', line).groups()
        self.lists[name].append(self.eval_expr(value))

    def remove_list(self, line):
        name, value = re.match(r'remove\("(.*)", (.*)\);', line).groups()
        val = self.eval_expr(value)
        if val in self.lists[name]:
            self.lists[name].remove(val)

    def list_length(self, line):
        name = re.match(r'List (\w+) length\(\);', line).group(1)
        print(len(self.lists[name]))

    def filter_list(self, line):
        name, cond = re.match(r'filter\("(.*)", (.*)\);', line).groups()
        self.lists[name] = [x for x in self.lists[name] if self.eval_cond(cond, x)]
