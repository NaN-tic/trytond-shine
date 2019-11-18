# This file is part shine module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import configuration
from . import ir
from . import shine
from . import table
from . import data
from . import tag
from . import function

def register():
    Pool.register(
        configuration.Configuration,
        ir.Cron,
        function.Function,
        shine.Sheet,
        shine.DataSet,
        shine.Formula,
        shine.View,
        shine.ViewTableFormula,
        table.Table,
        table.TableField,
        table.TableView,
        data.ModelAccess,
        data.Data,
        tag.Tag,
        tag.SheetTag,
        module='shine', type_='model')
