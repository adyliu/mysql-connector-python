# MySQL Connector/Python - MySQL driver written in Python.


try:
    from itertools import izip_longest as zip_longest
except ImportError:
    # Python 3
    from itertools import zip_longest

from django.db.models.sql import compiler


class SQLCompiler(compiler.SQLCompiler):
    def resolve_columns(self, row, fields=()):
        values = []
        index_extra_select = len(self.query.extra_select)
        bool_fields = ("BooleanField", "NullBooleanField")
        for value, field in zip_longest(row[index_extra_select:], fields):
            if (field and field.get_internal_type() in bool_fields and
                value in (0, 1)):
                value = bool(value)
            values.append(value)
        return row[:index_extra_select] + tuple(values)


class SQLInsertCompiler(compiler.SQLInsertCompiler, SQLCompiler):
    pass


class SQLDeleteCompiler(compiler.SQLDeleteCompiler, SQLCompiler):
    pass


class SQLUpdateCompiler(compiler.SQLUpdateCompiler, SQLCompiler):
    pass


class SQLAggregateCompiler(compiler.SQLAggregateCompiler, SQLCompiler):
    pass


class SQLDateCompiler(compiler.SQLDateCompiler, SQLCompiler):
    pass
