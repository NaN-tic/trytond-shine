import sql
import formulas
from datetime import datetime
from dateutil import relativedelta
from trytond import model
from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.i18n import gettext
from trytond.exceptions import UserWarning
from .shine import FIELD_TYPE_SQL, FIELD_TYPE_TRYTON, FIELD_TYPE_SELECTION

__all__ = ['Table', 'TableField', 'TableView']


class ModelEmulation:
    __doc__ = None
    _table = None
    __name__ = None


class Table(model.ModelSQL, model.ModelView):
    'Shine Table'
    __name__ = 'shine.table'
    name = model.fields.Char('Name', required=True)
    singleton = model.fields.Boolean('Singleton')
    fields = model.fields.One2Many('shine.table.field', 'table', 'Fields')
    views = model.fields.One2Many('shine.table.view', 'table', 'Views')

    def create_table(self):
        TableHandler = backend.get('TableHandler')

        model = ModelEmulation()
        model.__doc__ = self.name
        model._table = self.name

        if TableHandler.table_exist(self.name):
            TableHandler.drop_table('', self.name)

        table = TableHandler(model)

        for name, field in (('create_uid', fields.Integer),
                ('write_uid', fields.Integer),
                ('create_date', fields.Timestamp),
                ('write_date', fields.Timestamp)):
            sql_type = field._sql_type
            table.add_column(name, sql_type)

        for field in self.fields:
            sql_type = FIELD_TYPE_SQL[field.type]
            table.add_column(field.name, sql_type)
        return table

    def drop_table(self):
        transaction = Transaction()
        TableHandler = backend.get('TableHandler')
        TableHandler.drop_table('', self.name, cascade=True)
        transaction.database.sequence_delete(transaction.connection,
            self.name + '_id_seq')

    def copy_from(self, from_table):
        fields = {x.name for x in self.fields}
        from_fields = {x.name for x in from_table.fields}
        missing = sorted(list(from_fields - fields))

        existing = fields & from_fields
        fields = {}
        for field in self.fields:
            if field.name in existing:
                fields[field.name] = field.type

        different_types = []
        for field in from_table.fields:
            if field.name in existing:
                if (FIELD_TYPE_TRYTON[field.type] !=
                        FIELD_TYPE_TRYTON[fields[field.name]]):
                    different_types.append("%s (%s -> %s)" % (field.name,
                            field.type, fields[field.name]))
                    existing.remove(field.name)

        if missing or different_types:
            message = ['- %s' % x for x in (missing + different_types)]

            key = 'task_shine_copy_from_warning.%d' % self.id
            if Warning.check(key):
                raise UserWarning(
                    'shine_copy_from_warning.%s.%s' % (self.name, from_table.id),
                    gettext('shine.copy_from_warning', fields='\n'.join(message),
                        from_table=from_table.rec_name, table=self.rec_name))

        if not existing:
            return

        existing = sorted(list(existing))
        table = sql.Table(from_table.name)
        subquery = table.select()
        subquery.columns = [sql.Column(table, x) for x in existing]
        table = sql.Table(self.name)
        query = table.insert([sql.Column(table, x) for x in existing], subquery)

        cursor = Transaction().connection.cursor()
        cursor.execute(*query)

    def count(self):
        table = sql.Table(self.name)
        cursor = Transaction().connection.cursor()
        query = table.select(sql.aggregate.Count(1))
        cursor.execute(*query)
        return cursor.fetchone()[0]

    @classmethod
    def remove_old_tables(cls, days=0):
        Sheet = Pool().get('shine.sheet')
        current_table_ids = [x.current_table.id for x in Sheet.search([
                    ('current_table', '!=', None)])]
        tables = cls.search([
                ('create_date', '<', datetime.now() -
                    relativedelta.relativedelta(days=days)),
                ('id', 'not in', current_table_ids),
                ])
        cls.delete(tables)

    @classmethod
    def delete(cls, tables):
        for table in tables:
            table.drop_table()
        super(Table, cls).delete(tables)


from trytond.model import ModelSQL, ModelView, fields


class TableField(ModelSQL, ModelView):
    'Shine Table Field'
    __name__ = 'shine.table.field'
    table = fields.Many2One('shine.table', 'Table', required=True,
        ondelete='CASCADE')
    name = fields.Char('Name', required=True)
    string = fields.Char('String', required=True)
    type = fields.Selection([(None, '')] + FIELD_TYPE_SELECTION, 'Field Type',
        required=False)
    help = fields.Text('Help')
    related_model = fields.Many2One('ir.model', 'Related Model')
    formula = fields.Char('On Change With Formula')
    inputs = fields.Function(fields.Char('On Change With Inputs'), 'get_inputs')

    def get_inputs(self, name):
        if not self.formula:
            return
        parser = formulas.Parser()
        ast = parser.ast(self.formula)[1].compile()
        return (' '.join([x for x in ast.inputs])).lower()

    def get_ast(self):
        parser = formulas.Parser()
        ast = parser.ast(self.formula)[1].compile()
        return ast


class TableView(ModelSQL, ModelView):
    'Shine Table View'
    __name__ = 'shine.table.view'
    table = fields.Many2One('shine.table', 'Table', required=True,
        ondelete='CASCADE')
    type = fields.Char('Type')
    arch = fields.Text('Arch')
    system = fields.Boolean('System')
    field_names = fields.Char('Fields')
    field_childs = fields.Char('Field Childs')
