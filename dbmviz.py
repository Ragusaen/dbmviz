#!/usr/bin/env python3
import os
import re
import subprocess
import sys
import tempfile
import itertools

infinity = 100000

tikz_str_prefix = "\\documentclass{standalone}\n\n\\usepackage{xfp}\n\\usepackage{tikz}\n\\usetikzlibrary{calc, arrows.meta}\n\n\\newcommand{\\DBMPath}[6]{\n(\\fpeval{-(#3)},\\fpeval{-(#4)}) -- (\\fpeval{(#5) - (#4)}, \\fpeval{-(#4)}) -- (#1, \\fpeval{(#1) - (#5)}) -- (#1, #2) -- (\\fpeval{(#2) - (#6)}, #2) -- (\\fpeval{-(#3)}, \\fpeval{(#6) - (#3)}) -- cycle\n}\n\n\\newcommand{\\DBMAxes}[2]{\n\\coordinate (origin) at (0,0);\n\\node[label=above:$y$] (y-ext) at (0,#2 + 0.5) {};\n\\node[label=right:$x$] (x-ext) at (#1 + 0.5,0) {};\n\n\\foreach \\x in {0,..., #1}\n{\\node[label=below:$\\x$] (mark\\x) at (\\x, 0) {};\n\\draw ($(mark\\x) - (0,0.1)$) -- ($(mark\\x) + (0,0.1)$);}\n\\foreach \\y in {0,..., #2}\n{\\node[label=left:$\\y$] (mark\\y) at (0, \\y) {};\n\\draw ($(mark\\y) - (0.1,0)$) -- ($(mark\\y) + (0.1,0)$);}\n\n\\path[draw, ->]\n    (origin) edge (y-ext)\n    (origin) to (x-ext);\n}\n\n\n\\tikzset{Dot/.tip={Circle[length=4pt,sep=-2pt]}}\n\\newcommand{\\dbmyoffset}{0.3}\n\\newcommand{\\DBMAxis}[1]{\n\\coordinate (origin) at (0,0);\n\\node[label={[label distance=-3mm]right:$x$}] (x-ext) at (#1 + 0.5, -\\dbmyoffset) {};\n\n\\foreach \\x in {0,..., #1}\n{\\node[label=below:$\\x$] (mark\\x) at (\\x, -\\dbmyoffset) {};\n\\draw ($(mark\\x) - (0,0.1)$) -- ($(mark\\x) + (0,0.1)$);}\n\n\\path[draw, ->]\n    ($(origin) + (0, -\\dbmyoffset)$) to (x-ext);\n}\n\n\\begin{document}\n\\begin{tikzpicture}"
tikz_str_suffix = "\n\\end{tikzpicture}\n\\end{document}\n"

colors = ['red', 'green', 'blue', 'cyan', 'magenta', 'yellow']
color_iter = itertools.cycle(colors)


class DBM:
    @staticmethod
    def true(clocks: int):
        dbm = DBM(clocks)
        for c1 in range(1, clocks + 1):
            for c2 in range(clocks + 1):
                dbm[c1, c2] = infinity
        for c2 in range(clocks + 1):
            dbm[0, c2] = 0
        return dbm

    @staticmethod
    def false(clocks: int):
        dbm = DBM(clocks)
        dbm.dbm = [-1 for _ in range((clocks + 1)**2)]
        return dbm

    @staticmethod
    def zero(clocks: int):
        return DBM(clocks)

    # Input clocks is excluding 0-clock
    def __init__(self, clocks: int):
        self.clocks = clocks + 1 # Including 0-clock
        self.dbm = [0 for _ in range(self.clocks**2)]
        self.color = next(color_iter)

    def __getitem__(self, index: tuple[int, int]):
        return self.dbm[index[0] * self.clocks + index[1]]

    def __setitem__(self, index: tuple[int, int], value: int):
        self.dbm[index[0] * self.clocks + index[1]] = value

    def is_consistent(self):
        for c1 in range(self.clocks):
            for c2 in range(self.clocks):
                if -self[c1, c2] > self[c2, c1]:
                    return False
        return True

    def canonize(self):
        for c1 in range(self.clocks):
            for c2 in range(self.clocks):
                if c1 == c2:
                    continue
                c3 = self.clocks - c1 - c2
                if self[c1, c2] > self[c1, c3] + self[c3, c2]:
                    self[c1, c2] = self[c1, c3] + self[c3, c2] if self[c1, c3] != infinity and self[
                        c3, c2] != infinity else infinity

    def leq(self, clock1: int, clock2: int, value: int):
        self[clock1, clock2] = min(self[clock1, clock2], value)
        if not self.is_consistent():
            self.dbm = DBM.false().dbm
        self.canonize()

    def free(self, clock1: int, clock2: int):
        if clock1 == 0:
            self[0, clock2] = 0
        else:
            self[clock1, clock2] = infinity

    def reset(self, clock: int, value: int = 0):
        self[clock, 0] = value
        self[0, clock] = value
        for clock2 in range(1, self.clocks):
            if clock2 != clock:
                self[clock, clock2] = infinity
                self[clock2, clock] = infinity
        self.canonize()

    def copy(self):
        dbm = DBM(self.clocks - 1)
        dbm.dbm = self.dbm.copy()
        dbm.color = self.color
        return dbm

    def __eq__(self, other):
        return self.clocks == other.clocks and all(a == b for a, b in zip(self.dbm, other.dbm))

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        if self == DBM.true(self.clocks - 1):
            return "true"
        elif self == DBM.false(self.clocks - 1):
            return "false"

        if self.clocks <= 3:
            clock_names = [None, 'x', 'y']
        else:
            clock_names = [None] + [f'c{i}' for i in range(1, self.clocks)]

        c = []

        for c1 in range(1, self.clocks):
            if -self[0, c1] == self[c1, 0]:
                c.append(f"{clock_names[c1]}={self[c1, 0]}")
            else:
                if self[1, 0] != infinity:
                    c.append(f"{clock_names[c1]}<={self[1, 0]}")
                if self[0, 1] != 0:
                    c.append(f"{clock_names[c1]}>={-self[0, 1]}")

        for c1 in range(1, self.clocks):
            for c2 in range(c1 + 1, self.clocks):
                if -self[c1, c2] == self[c2, c1]:
                    c.append(f"{clock_names[c1]}-{clock_names[c2]}={self[c1, c2]}")
                else:
                    if self[2, 1] != infinity:
                        c.append(f"{clock_names[c2]}-{clock_names[c1]}<={self[c2, c1]}")
                    if self[1, 2] != infinity:
                        c.append(f"{clock_names[c1]}-{clock_names[c2]}<={self[c1, c2]}")

        return " and ".join(c)

dbms = {}

_current_name = "a"


def next_name():
    global _current_name
    name = _current_name
    _current_name = chr(ord(_current_name) + 1)
    return name


current_dbm = None

name_re = re.compile(r"[a-zA-Z0-9_']+")
constrain_re = re.compile(r"([a-zA-Z0-9_]+)\s*(<=|>=|<|>|=|==)\s*(-?\d+)")
diff_constrain_re = re.compile(r"([a-zA-Z0-9_]+)\s*-\s*([a-zA-Z0-9_]+)\s*(<=|>=|<|>|=|==)\s*(-?\d+)")

queued_commands = []


def get_input():
    global queued_commands
    if len(queued_commands) == 0:
        return input()
    else:
        c = queued_commands[0]
        queued_commands = queued_commands[1:]
        print(c)
        return c


if len(sys.argv) == 2:
    queued_commands = sys.argv[1].split(';')
elif len(sys.argv) != 1:
    print("Incorrect command usage, try dbmviz.py [commands]. Commands are in quotes and separated by ';'")
    exit(1)

while True:
    if current_dbm is None:
        print("-: ", end="")
    else:
        print(f"{current_dbm}: ", end="")

    command = get_input().split(' ')

    if len(command) == 0:
        pass

    elif command[0] == 'example':
        queued_commands += ['new zero', 'up', 'x <= 5', 'y>3', 'reset x', 'up', 'y<4', 'print', 'show']

    elif command[0] == "new":
        if len(command) < 2:
            print("Incorrect command usage, new <true|false|zero> [name]")
        else:
            name = command[2] if len(command) >= 3 else next_name()
            if name_re.fullmatch(name) is None:
                print("Incorrect name, must match [a-zA-Z0-9_']+")
                dbm = None
            elif command[1] == "true":
                dbm = DBM.true(2)
            elif command[1] == "false":
                dbm = DBM.false(2)
            elif command[1] == "zero":
                dbm = DBM.zero(2)
            else:
                print("Unknown DBM, try true, false or zero")
                continue

            dbms[name] = dbm
            current_dbm = name

    elif command[0] == 'copy':
        if current_dbm is None:
            print("No DBM selected, create one with the new command")
            continue
        if len(command) > 2:
            print('Incorrect command usage, copy [name of copy]')
            continue
        if len(command) == 1:
            name = current_dbm
            while name in dbms:
                name += '\''
        if len(command) == 2:
            if name_re.fullmatch(command[1]) is None:
                print("Incorrect name, must match [a-zA-Z0-9_']+")
                continue
            else:
                name = command[1]

        dbms[name] = dbms[current_dbm].copy()
        dbms[name].color = next(color_iter)
        current_dbm = name


    elif command[0] == "select":
        if len(command) != 2:
            print("Incorrect command usage, select <name>")
        elif not command[1] in dbms:
            print(f"I don't know the DBM '{command[1]}'")
        else:
            current_dbm = command[1]

    elif command[0] == "print":
        if current_dbm is None:
            print("No DBM selected, create one with the new command")
        elif len(command) == 2:
            if not command[1] in dbms:
                print(f"I don't know the DBM '{command[1]}'")
            else:
                print(dbms[command[1]])
        elif len(command) > 2:
            print("Incorrect command usage, print [name]")
        else:
            print(dbms[current_dbm])

    elif constrain_re.fullmatch(''.join(command)) is not None:
        match = constrain_re.fullmatch(''.join(command))
        dbm = dbms[current_dbm]

        if match[1] == "x":
            clock = 1
        elif match[1] == "y":
            clock = 2
        else:
            print(f"Unknown clock '{match[1]}', try x or y")
            continue

        value = int(match[3])
        if value < 0:
            print("Cannot constrain to negative value")
            continue

        if match[2] == "<=" or match[2] == "<":
            dbm.leq(clock, 0, value)
        elif match[2] == ">=" or match[2] == ">":
            dbm.leq(0, clock, -value)
        elif match[2] == "=" or match[2] == "==":
            dbm.leq(clock, 0, value)
            dbm.leq(0, clock, -value)

    elif diff_constrain_re.fullmatch(''.join(command)) is not None:
        match = diff_constrain_re.fullmatch(''.join(command))
        dbm = dbms[current_dbm]

        clock = [0, 0]
        for i in [1, 2]:
            if match[i] == "x":
                clock[i - 1] = 1
            elif match[i] == "y":
                clock[i - 1] = 2
            else:
                print(f"Unknown clock '{match[i]}', try x or y")
                continue

        value = int(match[4])

        if match[3] == "<=" or match[3] == "<":
            dbm.leq(clock[0], clock[1], value)
        elif match[3] == ">=" or match[3] == ">":
            dbm.leq(clock[1], clock[0], -value)
        elif match[3] == "=" or match[3] == "==":
            dbm.leq(clock[0], clock[1], value)
            dbm.leq(clock[1], clock[0], -value)

    elif command[0] == "up":
        if current_dbm is None:
            print("No DBM selected, create one with the new command")
        else:
            dbm = dbms[current_dbm]
            dbm.free(1, 0)
            dbm.free(2, 0)

    elif command[0] == "down":
        if current_dbm is None:
            print("No DBM selected, create one with the new command")
        else:
            dbm = dbms[current_dbm]
            dbm.free(0, 1)
            dbm.free(0, 2)

    elif command[0] == "reset":
        if current_dbm is None:
            print("No DBM selected, create one with the new command")
        else:
            dbm = dbms[current_dbm]
            if len(command) != 2:
                print("Incorrect command usage, reset <clock>")
            elif command[1] == "x":
                dbm.reset(1)
            elif command[1] == "y":
                dbm.reset(2)
            else:
                print(f"Unknown clock '{command[1]}', try x or y")

    elif command[0] == 'color':
        if current_dbm is None:
            print("No DBM selected, create one with the new command")
        else:
            dbm = dbms[current_dbm]
            if len(command) != 2:
                print("Incorrect command usage, color <color> // Any tikz color will work")
            else:
                dbm.color = command[1]

    elif command[0] == 'dbm':
        if current_dbm is None:
            print("No DBM selected, create one with the new command")
            continue

        dbm = dbms[current_dbm]


        def rep_inf(x):
            return '∞' if x == infinity else x


        names = ['0', 'x', 'y']
        s = " c-r<n " + ''.join(f'|  {s}  ' for s in names) + '\n'
        for x1, s1 in enumerate(names):
            s += '+'.join(['-' * 7] + ['-' * 5] * len(names)) + '\n'
            s += f'{s1: ^7}' + ''.join(f'|{rep_inf(dbm[x1, x2]): ^5}' for x2, _ in enumerate(names)) + '\n'

        print(s)

    elif command[0] == 'free':
        if current_dbm is None:
            print("No DBM selected, create one with the new command")
            continue

        cre = re.compile(r'([0xy])\s*-([0xy])\s*')
        if len(command) != 2 or not cre.fullmatch(''.join(command[1:])):
            print('Incorrect command usage, free <constraint>, e.g. x-0, 0-y, y-x, ...')

        dbm = dbms[current_dbm]
        match = cre.fullmatch(''.join(command[1:]))
        x1 = ['0', 'x', 'y'].index(match[1])
        x2 = ['0', 'x', 'y'].index(match[2])

        dbm.free(x1, x2)
        dbm.canonize()

    elif command[0] == 'extrapolate':
        if current_dbm is None:
            print("No DBM selected, create one with the new command")
            continue
        dbm = dbms[current_dbm]

        if len(command) > 3 or len(command) == 1:
            print('Incorrect command usage, extrapolate <constant>, or extrapolate <x constant> <y constant>')
            continue

        if not command[1].isdigit():
            print(f'{command[1]} is not an integer')
            continue
        M = [infinity] * 3
        M[1] = int(command[1])
        if len(command) == 2:
            M[2] = M[1]
        else:
            if not command[2].isdigit():
                print(f'{command[2]} is not an integer')
                continue
            M[2] = int(command[2])

        for x1 in [0,1,2]:
            for x2 in [0,1,2]:
                if x1 == x2:
                    continue
                if dbm[x1,x2] > M[x1]:
                    dbm[x1,x2] = infinity
                elif -dbm[x1,x2] > M[x2]:
                    dbm[x1,x2] = -M[x2]

        dbm.canonize()


    elif command[0] == 'LUextrapolate':
        if current_dbm is None:
            print("No DBM selected, create one with the new command")
            continue
        dbm = dbms[current_dbm]

        if len(command) != 5:
            print('Incorrect command usage, extrapolate <lower bound x> <upper bound x> <lower bound y> <upper bound y>')
            continue

        for i in range(1, len(command)):
            if not command[i].isdigit():
                print(f'{command[i]} is not an integer')
                continue
        L = [infinity, int(command[1]), int(command[3])]
        U = [infinity, int(command[2]), int(command[4])]

        for x1 in [0,1,2]:
            for x2 in [0,1,2]:
                if x1 == x2:
                    continue
                if dbm[x1,x2] > L[x1]:
                    dbm[x1,x2] = infinity
                elif -dbm[x1,x2] > U[x2]:
                    dbm[x1,x2] = -U[x2]

        dbm.canonize()


    elif command[0] == "show":
        show_dbms = []
        if len(command) == 1:
            command.append(current_dbm)

        fail = False
        for i in range(1, len(command)):
            if not command[i] in dbms:
                print(f"I don't know the DBM '{command[i]}'")
                fail = True
            else:
                show_dbms.append(dbms[command[i]])
        if fail:
            continue

        d = max((b for dbm in show_dbms for b in [dbm[1, 0], dbm[2, 0]] if b != infinity), default=infinity)
        if d == infinity:
            d = 5

        is_non2d = lambda dbm: dbm[1, 0] == -dbm[0, 1] or dbm[2, 0] == -dbm[0, 2] or dbm[1, 2] == -dbm[2, 1]
        show_dbms.sort(key=is_non2d)
        axes_index = next((i for i, dbm in enumerate(show_dbms) if is_non2d(dbm)), len(show_dbms))

        s = ""
        for i, dbm_raw in enumerate(show_dbms):
            dbm = dbm_raw.copy()
            if dbm[1, 0] == infinity:
                dbm[1, 0] = d + 0.5
            if dbm[2, 0] == infinity:
                dbm[2, 0] = d + 0.5
            dbm.canonize()

            if i == axes_index:
                s += "\\DBMAxes{" + str(d) + "}{" + str(d) + "}\n"

            if dbm[1, 0] == -dbm[0, 1] and dbm[2, 0] == -dbm[0, 2]:
                s += "\\node[circle, fill=" + dbm.color + "!80, inner sep=1.5] at (" + str(dbm[1, 0]) + "," + str(
                    dbm[2, 0]) + ") {}; "
            else:
                if is_non2d(dbm):
                    s += "\\draw[" + dbm.color + "!80, ultra thick] "
                else:
                    s += "\\path[fill=" + dbm.color + "!80] "
                s += "\\DBMPath{" + str(dbm[1, 0]) + "}{" + str(dbm[2, 0]) + "}{" + str(dbm[0, 1]) + "}{" + str(
                    dbm[0, 2]) + "}{" + str(dbm[1, 2]) + "}{" + str(dbm[2, 1]) + "}; \n"

        if len(show_dbms) == axes_index:
            s += "\\DBMAxes{" + str(d) + "}{" + str(d) + "}\n"

        dir = tempfile.mkdtemp(None, f'dbmviz_')
        with open(os.path.join(dir, 'dbm.tex'), 'w') as f:
            f.write(tikz_str_prefix + s + tikz_str_suffix)
        p = subprocess.run(['pdflatex', '-halt-on-error', 'dbm.tex'], cwd=dir, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
        if p.returncode != 0:
            print(p.stdout.decode('utf-8'))
            print(p.stderr.decode('utf-8'))
            print(f"Unfortunately something went wrong, check the .tex file {os.path.join(dir, 'dbm.tex')}")
            continue

        subprocess.Popen(['xdg-open', 'dbm.pdf'], cwd=dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    elif command[0] == "tikz":
        dbm = None
        if len(command) > 2:
            print("Incorrect command usage, tikz [name]")
            continue
        elif len(command) == 2:
            if not command[1] in dbms:
                print(f"I don't know the DBM '{command[1]}'")
                continue
            else:
                dbm = dbms[command[1]]
        else:
            dbm = dbms[current_dbm]

        dir = tempfile.mkdtemp(None, f'dbmviz_')
        d = max(dbm[1, 0], dbm[2, 0])
        if d == infinity:
            d = 5
        dbm = dbm.copy()
        if dbm[1, 0] == infinity:
            dbm[1, 0] = d + 0.5
        if dbm[2, 0] == infinity:
            dbm[2, 0] = d + 0.5
        dbm.canonize()

        s = ""
        if dbm[1, 0] == -dbm[0, 1] and dbm[2, 0] == -dbm[0, 2]:
            s += "\\DBMAxes{" + str(d) + "}{" + str(d) + "}\n"
            s += "\\node[circle, fill=" + dbm.color + "!80, inner sep=1.5] at (" + str(dbm[1, 0]) + "," + str(
                dbm[2, 0]) + ") {}; "
        else:
            is_non2d = dbm[1, 0] == -dbm[0, 1] or dbm[2, 0] == -dbm[0, 2] or dbm[1, 2] == -dbm[2, 1]
            if is_non2d:
                s += "\\DBMAxes{" + str(d) + "}{" + str(d) + "}\n"
                s += "\\draw[" + dbm.color + "!80, ultra thick] "
            else:
                s += "\\path[fill=" + dbm.color + "!80] "
            s += "\\DBMPath{" + str(dbm[1, 0]) + "}{" + str(dbm[2, 0]) + "}{" + str(dbm[0, 1]) + "}{" + str(
                dbm[0, 2]) + "}{" + str(dbm[1, 2]) + "}{" + str(dbm[2, 1]) + "}; \n"
            if not is_non2d:
                s += "\\DBMAxes{" + str(d) + "}{" + str(d) + "}"
        print(s)

    elif command[0] == "tikz-help":
        print(
            """To render the tikz output in latex, you must define these two macros once in your document:
\\newcommand{\\DBMPath}[6]{
(\\fpeval{-(#3)},\\fpeval{-(#4)}) -- (\\fpeval{(#5) - (#4)}, \\fpeval{-(#4)}) -- (#1, \\fpeval{(#1) - (#5)}) -- (#1, #2) -- (\\fpeval{(#2) - (#6)}, #2) -- (\\fpeval{-(#3)}, \\fpeval{(#6) - (#3)}) -- cycle
}

\\newcommand{\\DBMAxes}[2]{
\\coordinate (origin) at (0,0);
\\node[label=above:$y$] (y-ext) at (0,#2 + 0.5) {};
\\node[label=right:$x$] (x-ext) at (#1 + 0.5,0) {};

\\foreach \\x in {0,..., #1}
{\\node[label=below:$\\x$] (mark\\x) at (\\x, 0) {};
\\draw ($(mark\\x) - (0,0.1)$) -- ($(mark\\x) + (0,0.1)$);}
\\foreach \\y in {0,..., #2}
{\\node[label=left:$\\y$] (mark\\y) at (0, \\y) {};
\\draw ($(mark\\y) - (0.1,0)$) -- ($(mark\\y) + (0.1,0)$);}

\path[draw, ->]
    (origin) edge (y-ext)
    (origin) to (x-ext);
}

\\tikzset{Dot/.tip={Circle[length=4pt,sep=-2pt]}}
\\newcommand{\\dbmyoffset}{0.3}
\\newcommand{\\DBMAxis}[1]{
\\coordinate (origin) at (0,0);
\\node[label={[label distance=-3mm]right:$x$}] (x-ext) at (#1 + 0.5, -\\dbmyoffset) {};

\\foreach \\x in {0,..., #1}
{\\node[label=below:$\\x$] (mark\\x) at (\\x, -\\dbmyoffset) {};
\\draw ($(mark\\x) - (0,0.1)$) -- ($(mark\\x) + (0,0.1)$);}

\\path[draw, ->]
    ($(origin) + (0, -\\dbmyoffset)$) to (x-ext);
}

You will then also need these packages:
\\usepackage{xfp}
\\usepackage{tikz}
\\usetikzlibrary{calc, arrows.meta}


Finally, to render the DBM, simply place the macro calls into a tikzpicture environment, e.g.:
\\begin{tikzpicture}
\path[fill=red!80] \DBMPath{4}{2}{-1}{0}{2}{0};
\DBMAxes{4}{4}
\\end{tikzpicture}
"""
        )


    elif command[0] == "quit":
        exit(0)

    elif command[0] == "help":
        print(
            """This is an interactive tool to play with Difference Bound Matrices (DBMs).
Commands:
example - runs the example from below
new <true|false|zero> [name] - Create a new DBM, if no name is given, a new name is generated
select <name> - Select a DBM
copy [name] - Copy the current DBM, optionally give it a name
print [name] - Print a DBM, if no name is given, print the selected DBM
<clock> op <value> - For op ∈ {<=,<,=,==,>,>=}. Constrain a clock to a value; no difference between strict and non-strict
<clock1> - <clock2> op <value> - For op ∈ {<=,<,=,==,>,>=}. Constrain the difference between two clocks to a value
up - Free upper constraints
down - Free lower constraints
free <clock1> - <clock2> - Free a specific constraint, can involve the 0 clock
reset <clock> - Reset a clock to 0
extrapolate <constant> - Extrapolate with the max constant as <constant> for all clocks
extrapolate <constant x> <constant y> - Extrapolate with a seperate constant for each clock
tikz [name] - Prints the tikz commands to draw the DBM, see tikz-help for more information
tikz-help - Explains how to render the tikz output in latex
help - Print this help message
quit - Exit the program

Example:
new zero // Creates a new DBM with exactly one valuation (0,0)
up // Free upper constrains (unbounded delay)
x <= 5 // Constrain x to less than 5
y>3 // There is no difference between strict and non-strict inequalities
reset x // Reset the x clock to 0
up
y<4
print // Print the constraints of the current DBM, the constraints x >= 0, y >= 0, x <= ∞, y <= ∞, x - y <= ∞, y - x <= ∞ are not shown
show // Shows a visual presentation of the DBM
""")

    else:
        print(f"Unknown command '{command[0]}', try help for a list of commands")