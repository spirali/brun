import argparse
import subprocess
import time
import threading
import itertools

from table import Table

class Benchmark(object):

    def __init__(self, command, info=None, post_fn=None, shell=False):
        if info is not None:
            self.info = info
        else:
            self.info = {}

        if isinstance(command, str):
            if shell:
                self.command = command
            else:
                self.command = command.split()
            self.info["command"] = command
        else:
            self.command = command
            self.info["command"] = " ".join(command)

        if post_fn is None:
            self.post_fns = []
        elif hasattr(post_fn, '__iter__'):
            self.post_fns = list(post_fn)
        else:
            self.post_fns = [ post_fn ]

        self.shell = shell

    def add_post_fn(self, fn):
        self.post_fns.append(fn)

    def execute(self, cwd=None, timeout=None):
        p = subprocess.Popen(self.command,
                             cwd=cwd,
                             stdout=None,
                             shell=self.shell)
        def target():
            p.wait()
        thread = threading.Thread(target=target)
        tm = time.time()
        thread.start()
        thread.join(timeout)
        tm = time.time() - tm
        if thread.is_alive():
            if p:
                p.terminate()
            thread.join()
            return "timeout"
        else:
            if p.returncode != 0:
                return "failed"
            return tm

    def run(self, context):
        result = self.info.copy()
        if self in context.skip_list:
            result["status"] = "skipped"
            return result
        status = self.execute(None, context.timeout)
        if not isinstance(status, str):
            result["status"] = "ok"
            result["time"] = status
        else:
            result["status"] = status
        for fn in self.post_fns:
            fn(context, result)
        return result

    def get(self, key):
        return self.info.get(key)

    def __repr__(self):
        return "<Benchmark command='{0}'>".format(self.command)


class Context:

    def __init__(self, benchmarks, timeout):
        self.benchmarks = benchmarks
        self.skip_list = set()
        self.timeout = timeout

    def skip(self, predicate):
        for benchmark in self.benchmarks:
            if predicate(benchmark):
                self.skip_list.add(benchmark)

    def run(self):
        results = []
        for i, benchmark in enumerate(self.benchmarks):
            print "================ [{0}/{1}] =================" \
                    .format(i + 1, len(self.benchmarks))
            print "Command:", benchmark.info["command"]
            result = benchmark.run(self)
            results.append(result)
            if result["status"] == "ok":
                print "Time:   ", result["time"]
            else:
                print "Status: ", result["status"]
        return results


_all_benchmarks = []

def add(*args, **kw):
    _all_benchmarks.append(Benchmark(*args, **kw))

def make_product(dictionary):
    keys = dictionary.keys()
    values = [ dictionary[k] for k in keys ]
    for v in itertools.product(*values):
        yield dict(zip(keys, v))

def make_set(command_pattern, fixed_info, info, *args, **kw):
    for d in make_product(info):
        new_info = fixed_info.copy()
        new_info.update(d)
        yield Benchmark(
                command_pattern.format(**new_info), new_info, *args, **kw)

def add_set(command_pattern, fixed_info, info, *args, **kw):
    _all_benchmarks.extend(list(make_set(
        command_pattern, fixed_info, info, *args, **kw)))

def _parse_args():
    parser = argparse.ArgumentParser(description=
            "brun -- Benchmark runner")

    parser.add_argument("-f",
                        metavar="FILTER",
                        type=str,
                        help="Filter benchmarks")

    parser.add_argument("-c",
                        nargs="*",
                        help="Select columns")

    parser.add_argument("-H",
                        nargs="*",
                        help="Hide columns")

    parser.add_argument("--list",
                        action="store_true",
                        help="Print all benchmarks")

    parser.add_argument("--transpose",
                        action="store_true",
                        help="Print all benchmarks")

    parser.add_argument("--tab2",
                        nargs=3,
                        type=str,
                        help="Print all benchmarks")


    parser.add_argument("--timeout",
                        type=float,
                        help="Timeout of tests [s]")


    return parser.parse_args()

def _parse_filter(s):
    if "=" in s:
        return ["="] + s.split("=")
    if "~" in s:
        return ["~"] + s.split("~")
    return "*", s, ""

def _filter(args, benchmarks):
    if args.f is None:
        return benchmarks
    op, key, value = _parse_filter(args.f)
    results = []
    for benchmark in benchmarks:
        v = benchmark.info.get(key)
        if v is None:
            continue
        if op == "=":
            if v != value:
                continue
        if op == "~":
            if value not in v:
                continue
        results.append(benchmark)
    return results

def make_table(items, args):
    table = Table()
    if args.c is None:
        columns = _get_names(items)
        if args.H:
            columns = [ name for name in columns if name not in args.H ]
    else:
        columns = args.c
    table.add_dictionaries(items, columns)
    return table

def _get_names(items):
    lst = list(set().union(*(item.keys() for item in items)))
    lst.sort()
    return lst

def _get_values(items, key):
    lst = list(set(filter(lambda x: x is not None,
                          (item.get(key) for item in items))))
    lst.sort()
    return lst

def tabularize(items, column1, column2, data_column, merge_fn):
    x_values = _get_values(items, column2)
    y_values = _get_values(items, column1)
    results = [ [ column1 ] + x_values ]
    for y_name in y_values:
        row = [ y_name ]
        for x_name in x_values:
            values = None
            for item in items:
                v1 = item.get(column2)
                v2 = item.get(column1)
                if v1 == x_name and v2 == y_name:
                    value = item.get(data_column)
                    if value is not None:
                        values = merge_fn(values, value)
            row.append(values)
        results.append(row)
    return results

def make_table2(items, column1, column2, data_column):
    def merge_fn(values, value):
        if values is None:
            return value
        elif isinstance(values, list):
            return values.append(value)
        else:
            return [ values, value ]

    rows = tabularize(items, column1, column2, data_column, merge_fn)
    table = Table()
    table.add_rows(rows)
    return table

def main(timeout=None, post_fn=None):
    args = _parse_args()

    if args.timeout is None:
        args.timeout = timeout

    benchmarks = _filter(args, _all_benchmarks)

    if post_fn:
        for benchmark in benchmarks:
            benchmark.add_post_fn(post_fn)

    if not benchmarks:
        print "No benchmarks to execute"
        return

    if args.list:
        results = [b.info for b in benchmarks]
    else:
        results = Context(benchmarks, args.timeout).run()

    if args.tab2:
        table = make_table2(
            results, args.tab2[0], args.tab2[1], args.tab2[2])
    else:
        table = make_table(results, args)
    if args.transpose:
        table = table.transpose()
    print
    print table.to_ascii_table(),

    with open("results.py", "w") as f:
        f.write("results = [\n")
        for result in results:
            f.write("    " + repr(result) + ",\n")
        f.write("]\n")
    print "Full results written into 'results.py'"
