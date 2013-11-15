# MySQL Connector/Python - MySQL driver written in Python.


from django.db import models
from django.db.backends.creation import BaseDatabaseCreation


class DatabaseCreation(BaseDatabaseCreation):
    """Maps Django Field object with MySQL data types
    """
    def __init__(self, connection):
        super(DatabaseCreation, self).__init__(connection)

        self.data_types = {
            'AutoField': 'integer AUTO_INCREMENT',
            'BooleanField': 'bool',
            'CharField': 'varchar(%(max_length)s)',
            'CommaSeparatedIntegerField': 'varchar(%(max_length)s)',
            'DateField': 'date',
            'DateTimeField': 'datetime',  # ms support set later
            'DecimalField': 'numeric(%(max_digits)s, %(decimal_places)s)',
            'FileField': 'varchar(%(max_length)s)',
            'FilePathField': 'varchar(%(max_length)s)',
            'FloatField': 'double precision',
            'IntegerField': 'integer',
            'BigIntegerField': 'bigint',
            'IPAddressField': 'char(15)',
            'GenericIPAddressField': 'char(39)',
            'NullBooleanField': 'bool',
            'OneToOneField': 'integer',
            'PositiveIntegerField': 'integer UNSIGNED',
            'PositiveSmallIntegerField': 'smallint UNSIGNED',
            'SlugField': 'varchar(%(max_length)s)',
            'SmallIntegerField': 'smallint',
            'TextField': 'longtext',
            'TimeField': 'time',  # ms support set later
        }

        # Support for microseconds
        if self.connection.get_server_version() >= (5, 6, 4):
            self.data_types.update({
                'DateTimeField': 'datetime(6)',
                'TimeField': 'time(6)',
            })

    def sql_table_creation_suffix(self):
        suffix = []
        if self.connection.settings_dict['TEST_CHARSET']:
            suffix.append('CHARACTER SET {0}'.format(
                self.connection.settings_dict['TEST_CHARSET']))
        if self.connection.settings_dict['TEST_COLLATION']:
            suffix.append('COLLATE {0}'.format(
                self.connection.settings_dict['TEST_COLLATION']))
        return ' '.join(suffix)

    def sql_for_inline_foreign_key_references(self, field, known_models,
                                              style):
        "All inline references are pending under MySQL"
        return [], True

    def sql_for_inline_many_to_many_references(self, model, field, style):
        opts = model._meta
        qn = self.connection.ops.quote_name

        columndef = '    {column} {type} {options},'
        table_output = [
            columndef.format(
                column=style.SQL_FIELD(qn(field.m2m_column_name())),
                type=style.SQL_COLTYPE(models.ForeignKey(model).db_type(
                    connection=self.connection)),
                options=style.SQL_KEYWORD('NOT NULL')
            ),
            columndef.format(
                column=style.SQL_FIELD(qn(field.m2m_reverse_name())),
                type=style.SQL_COLTYPE(models.ForeignKey(field.rel.to).db_type(
                    connection=self.connection)),
                options=style.SQL_KEYWORD('NOT NULL')
            ),
        ]

        deferred = [
            (field.m2m_db_table(), field.m2m_column_name(), opts.db_table,
                opts.pk.column),
            (field.m2m_db_table(), field.m2m_reverse_name(),
                field.rel.to._meta.db_table, field.rel.to._meta.pk.column)
        ]
        return table_output, deferred
