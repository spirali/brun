
class Table(object):

    def __init__(self):
        self.rows = []


    def to_ascii_table(self):
        if not self.rows:
            return ""
        lines = []
        def print_row(row):
            line = ""
            for column, l in zip(row, lens):
                if column is None:
                    s = ""
                else:
                    s = str(column)
                line += "| " + s + " " * (l - len(s)) + " "
            line += "|\n"
            lines.append(line)

        lens = []
        for i, column in enumerate(self.rows[0]):
            lens.append(max(len(str(r[i]))
                            for r in self.rows if r[i] is not None))
        width = sum(lens) + 3 * len(self.rows[0]) + 1
        separator = ("-" * width) + "\n"

        lines.append(separator)
        print_row(self.rows[0])
        lines.append(separator)

        if len(self.rows) == 1:
            return
        for row in self.rows[1:]:
            print_row(row)
        lines.append(separator)
        return "".join(lines)

    def transpose(self):
        if not self.rows:
            return

        table = Table()
        for i in xrange(len(self.rows[0])):
            table.add_row([ r[i] for r in self.rows ])
        return table

    def add_row(self, data):
        self.rows.append(data)

    def add_rows(self, rows):
        self.rows.extend(rows)

    def add_dictionaries(self, items, columns):
        self.add_row(columns)
        for item in items:
            row = [ item.get(column) for column in columns ]
            self.add_row(row)
