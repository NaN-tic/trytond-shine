import sql
import formulas
import schedula
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.tools import cursor_dict
from trytond.pyson import PYSONEncoder
from trytond.i18n import gettext
from trytond.exceptions import UserError
from .shine import FIELD_TYPE_TRYTON, FIELD_TYPE_CAST

__all__ = ['ModelAccess', 'Data']


class Adapter:
    def __getattr__(self, name):
        fields = self.get_fields()
        return getattr(fields, name)

    def __contains__(self, key):
        fields = self.get_fields()
        return fields.__contains__(key)

    def __iter__(self):
        fields = self.get_fields()
        return fields.__iter__()

    def __getitem__(self, name):
        fields = self.get_fields()
        return fields.__getitem__(name)

    def get_fields(self):
        # TODO: Cache
        Data = Pool().get('shine.data')
        table = Data.get_table()
        if not table:
            return Data._previous_fields
        res = {}
        for field in table.fields:
            if field.type == 'char':
                obj = fields.Char(field.string)
            elif field.type == 'multiline':
                obj = fields.Text(field.string)
            elif field.type == 'integer':
                obj = fields.Integer(field.string)
            elif field.type == 'float':
                obj = fields.Float(field.string)
            elif field.type == 'boolean':
                obj = fields.Boolean(field.string)
            elif field.type == 'numeric':
                obj = fields.Numeric(field.string)
            elif field.type == 'date':
                obj = fields.Date(field.string)
            elif field.type == 'datetime':
                obj = fields.DateTime(field.string)
            elif field.type == 'timestamp':
                obj = fields.Timestamp(field.string)
            elif field.type == 'many2one':
                obj = fields.Many2One(field.related_model.model, field.string)
            elif field.type in ('binary', 'icon'):
                obj = fields.Binary(field.string)
            obj.name = field.name
            res[field.name] = obj
        if not 'id' in res:
            obj = fields.Integer('ID')
            obj.name = 'id'
            res[field.name] = obj

        return res


class ModelAccess(metaclass=PoolMeta):
    __name__ = 'ir.model.access'

    @classmethod
    def check_relation(cls, model_name, field_name, mode='read'):
        '''
        We must override check_relation and ensure that super() does not
        execute:

        getattr(Model, fieldname)

        because the fields do not exist in the Model. If super() used
        Model._fields[fieldname] we would not be forced to override the method.
        '''
        if model_name == 'shine.data':
            return True
        return super(ModelAccess, cls).check_relation(model_name, field_name,
            mode)


class Data(ModelSQL, ModelView):
    'Shine Data'
    __name__ = 'shine.data'

    @classmethod
    def __post_setup__(cls):
        super(Data, cls).__post_setup__()
        cls._previous_fields = cls._fields
        cls._fields = Adapter()

    @classmethod
    def __setup__(cls):
        super(Data, cls).__setup__()
        cls.__rpc__['fields_view_get'].cache = None
        cls.__rpc__['default_get'].cache = None

    @classmethod
    def __table__(cls):
        # TODO: Check if we can drop create(), read(), write(), delete() &
        # search()
        return cls.get_sql_table()

    @classmethod
    def default_get(cls, fields_names, with_rec_name=True):
        table = cls.get_table()

        if not table.singleton:
            return {}
        default = {}
        singleton = cls.get_singleton()
        if singleton:
            if with_rec_name:
                fields_names = fields_names[:]
                for field in fields_names[:]:
                    if cls._fields[field]._type in ('many2one',):
                        fields_names.append(field + '.rec_name')
            default, = cls.read([singleton.id], fields_names=fields_names)
            del default['id']
        return default

    def on_change_with(self, fieldnames):
        table = self.get_table()
        res = {}
        for field in table.fields:
            if not field.name in fieldnames:
                continue
            ast = field.get_ast()
            inputs = field.inputs.split()
            inputs = [getattr(self, x) for x in inputs]
            try:
                value = ast(*inputs)
            except schedula.utils.exc.DispatcherError as e:
                raise UserError(gettext('shine.msg_service_message',
                    message=e.args[0] % e.args[1:]))

            if isinstance(value, list):
                value = str(value)
            elif (not isinstance(value, str)
                    and not isinstance(value, int)
                    and not isinstance(value, float)
                    and not isinstance(value, type(None))):
                value = value.tolist()
            if isinstance(value, formulas.tokens.operand.XlError):
                value = None
            res[field.name] = value
        return res

    @classmethod
    def fields_get(cls, fields_names=None):
        Model = Pool().get('ir.model')
        res = super(Data, cls).fields_get(fields_names)
        table = cls.get_table()
        for field in table.fields:
            res[field.name] = {
                'name': field.name,
                'string': field.string,
                'type': FIELD_TYPE_TRYTON[field.type],
                'relation': (field.related_model.model if
                    field.related_model else None),
                'readonly': bool(field.formula),
                'help': field.help,
                }
            if field.inputs:
                res[field.name]['on_change_with'] = field.inputs.split()
            if field.type == 'reference':
                selection = []
                for model in Model.search([]):
                    selection.append((model.model, model.name))
                res[field.name]['selection'] = selection
            if field.type == 'timestamp':
                res[field.name]['format'] = PYSONEncoder().encode('%H:%M:%S.%f')
        return res

    @classmethod
    def fields_view_get(cls, view_id=None, view_type='form', level=None):
        table = cls.get_table()
        view = cls.get_table_view()

        if not view:
            for view in table.views:
                if not view.system:
                    continue
                if view.type == view_type:
                    break
            assert(view.id)

        res = {
            'type': view.type,
            'view_id': view_id,
            'field_childs': None,
            'arch': view.arch,
            # TODO: We should specify the exact fields required by the view
            'fields': cls.fields_get(),
            }
        return res

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        if not cls.get_table():
            return super(Data, cls).search(domain, offset, limit, order, count,
                query)
        table = cls.get_sql_table()
        cursor = Transaction().connection.cursor()
        # Get domain clauses
        tables, expression = cls.search_domain(domain,
            tables={None: (table, None)})

        select = table.select(table.id, where=expression, limit=limit,
            offset=offset)
        if query:
            return select
        cursor.execute(*select)
        res = [x[0] for x in cursor.fetchall()]
        return cls.browse(res)

    @classmethod
    def read(cls, ids, fields_names=None):
        sql_table = cls.get_sql_table()
        table = cls.get_table()

        if not ids:
            return []

        cursor = Transaction().connection.cursor()
        cursor.execute(*sql_table.select(where=sql_table.id.in_(ids)))
        fetchall = list(cursor_dict(cursor))

        to_cast = {}
        for field in table.fields:
            if fields_names and not field.name in fields_names:
                continue
            cast = FIELD_TYPE_CAST[field.type]
            if cast:
                to_cast[field.name] = cast

        if to_cast:
            for record in fetchall:
                for field, cast in to_cast.items():
                    record[field] = cast(record[field])
        return fetchall

    @classmethod
    def create(cls, vlist):
        table = cls.get_table()
        if table.singleton:
            assert len(vlist) == 1
            singleton = cls.get_singleton()
            if singleton:
                cls.write([singleton], vlist[0])
                return [singleton]

        sql_table = cls.get_sql_table()

        cursor = Transaction().connection.cursor()
        ids = []
        for record in vlist:
            fields = []
            values = []
            for key, value in record.items():
                fields.append(sql.Column(sql_table, key))
                values.append(value)

            query = sql_table.insert(fields, values=[values],
                returning=[sql_table.id])
            cursor.execute(*query)
            ids.append(cursor.fetchone()[0])
        records = cls.browse(ids)
        cls.update_formulas(records)
        return records

    @classmethod
    def update_formulas(cls, records=None):
        table = cls.get_table()
        if not records:
            records = cls.search([])

        formula_fields = [x.name for x in table.fields if x.formula]
        if not formula_fields:
            return
        actions = []
        for record in records:
            actions.append([record])
            actions.append(record.on_change_with(formula_fields))
        cls.write(*actions)

    @classmethod
    def write(cls, *args):
        table = cls.get_table()
        formula_fields = [x.name for x in table.fields if x.formula]

        table = cls.get_sql_table()
        cursor = Transaction().connection.cursor()

        has_formulas = False
        all_records = []
        actions = iter(args)
        for records, values in zip(actions, actions):
            all_records += records
            fields = []
            to_update = []
            for key, value in values.items():
                fields.append(sql.Column(table, key))
                to_update.append(value)
                if key in formula_fields:
                    has_formulas = True
            query = table.update(fields, to_update,
                where=table.id.in_([x.id for x in records]))
            cursor.execute(*query)

        if not has_formulas and formula_fields:
            cls.update_formulas(all_records)

    @classmethod
    def delete(cls, records):
        table = cls.get_table()
        if table.singleton:
            singleton = cls.get_singleton()
            if singleton:
                records = [singleton]

        sql_table = cls.get_sql_table()
        cursor = Transaction().connection.cursor()
        ids = [x.id for x in records if x.id > 0]
        if ids:
            query = sql_table.delete(where=sql_table.id.in_(ids))
            cursor.execute(*query)

    @classmethod
    def copy(cls, records, default=None):
        records = cls.read([x.id for x in records if x.id])
        for record in records:
            del record['id']
        return cls.create(records)

    @classmethod
    def get_singleton(cls):
        # From modelsingleton.py
        '''
        Return the instance of the unique record if there is one.
        '''
        singletons = cls.search([], limit=1)
        if singletons:
            return singletons[0]

    @classmethod
    def get_sheet(cls):
        Sheet = Pool().get('shine.sheet')
        sheet_id = Transaction().context.get('shine_sheet')
        if sheet_id:
            return Sheet(sheet_id)
        view = cls.get_view()
        if view:
            return view.sheet

    @classmethod
    def get_view(cls):
        View = Pool().get('shine.view')
        view_id = Transaction().context.get('shine_view')
        if view_id:
            return View(view_id)

    @classmethod
    def get_table_view(cls):
        TableView = Pool().get('shine.table.view')
        table_view_id = Transaction().context.get('shine_table_view')
        if table_view_id:
            return TableView(table_view_id)
        view = cls.get_view()
        if view:
            return view.current_table_view

    @classmethod
    def get_table(cls):
        Table = Pool().get('shine.table')
        table = Transaction().context.get('shine_table')
        if Pool().test:
            # Tryton default tests try to get data using '1' as active_id
            # We prevent the tests from failing by returning no table
            return
        if not table:
            sheet = cls.get_sheet()
            if sheet:
                table = sheet.current_table
        if not table:
            view = cls.get_view()
            if view:
                return view.current_table
        if table:
            return Table(table)

    @classmethod
    def get_sql_table(cls):
        table = cls.get_table()
        if table:
            return sql.Table(table.name)
        return super(Data, cls).__table__()
