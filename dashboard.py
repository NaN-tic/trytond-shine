from trytond.model import ModelSQL, ModelView, fields, sequence_ordered
from trytond.pool import Pool
from trytond.pyson import PYSONEncoder

__all__ = ['Dashboard', 'DashboardElement', 'DashboardMockup']


class Dashboard(ModelSQL, ModelView):
    'Shine Dashboard'
    __name__ = 'shine.dashboard'
    name = fields.Char('Name', required=True)
    responsive = fields.Boolean('Responsive')
    elements = fields.One2Many('shine.dashboard.element', 'dashboard',
        'Elements')
    mockup = fields.One2Many('shine.dashboard.mockup', 'dashboard', 'Mockup',
        readonly=True)

    @classmethod
    def update_mockups(cls, dashboards):
        for dashboard in dashboards:
            dashboard.update_mockup()

    @classmethod
    def create(cls, vlist):
        res = super(Dashboard, cls).create(vlist)
        cls.update_mockups(res)
        return res

    @classmethod
    def write(cls, *args):
        super(Dashboard, cls).write(*args)
        records = []
        actions = iter(args)
        for dashboards, values in zip(actions, actions):
            records += dashboards
        cls.update_mockups(records)

    def update_mockup(self):
        Mockup = Pool().get('shine.dashboard.mockup')
        Mockup.delete([x for x in self.mockup])

        count = max([x.bottom for x in self.elements])
        matrix = [[''] * 12] * count

        for element in self.elements:
            for row in range(element.top - 1, element.bottom):
                for column in range(element.left - 1, element.right):
                    matrix[row][column] = element.alias
        print('M: %s' % '\n'.join([str(x) for x in matrix]))

        mockups = []
        sequence = 0
        for row in matrix:
            sequence += 1
            mockup = Mockup()
            mockup.dashboard = self
            mockup.sequence = sequence
            for column in range(len(row)):
                setattr(mockup, 'column%d' % (column + 1), row[column])
            mockups.append(mockup)

        Mockup.save(mockups)


class DashboardElement(sequence_ordered(), ModelSQL, ModelView):
    'Shine Dashboard Element'
    __name__ = 'shine.dashboard.element'
    dashboard = fields.Many2One('shine.dashboard', 'Dashboard', required=True,
        ondelete='CASCADE')
    alias = fields.Char('Alias', required=True, size=1)
    view = fields.Many2One('shine.view', 'View', required=True)
    action = fields.Many2One('ir.action.act_window', 'Action')
    left = fields.Integer('Left Column')
    right = fields.Integer('Right Column')
    top = fields.Integer('Top Row')
    bottom = fields.Integer('Bottom Row')

    @fields.depends('alias')
    def on_change_alias(self):
        if self.alias:
            self.alias = self.alias.upper()

    @classmethod
    def create(cls, vlist):
        res = super(DashboardElement, cls).create(vlist)
        cls.create_actions(res)
        return res

    @classmethod
    def write(cls, *args):
        super(DashboardElement, cls).write(*args)
        actions = iter(args)
        to_update = []
        for elements, values in zip(actions, actions):
            to_update += elements
        cls.update_actions(to_update)

    @classmethod
    def delete(cls, elements):
        super(DashboardElement, cls).delete(elements)
        cls.delete_actions(elements)

    @classmethod
    def create_actions(cls, elements):
        ActWindow = Pool().get('ir.action.act_window')

        for element in elements:
            action = ActWindow()
            action.name = element.alias
            action.res_model = 'shine.data'
            action.usage = 'dashboard'
            action.context = PYSONEncoder().encode({
                    'shine_view': element.view.id,
                    'shine_sheet': element.view.sheet.id,
                    'shine_table': element.view.sheet.current_table.id,
                    })
            action.save()
            element.action = action
            element.save()

    @classmethod
    def update_actions(cls, elements):
        to_create = []
        for element in elements:
            if not element.action:
                to_create.append(element)
                continue
            action = element.action
            action.name = element.alias
            action.res_model = 'shine.data'
            action.usage = 'dashboard'
            action.context = PYSONEncoder().encode({
                    'shine_view': element.view.id,
                    'shine_sheet': element.view.sheet.id,
                    'shine_table': element.view.sheet.current_table.id,
                    })
            action.save()
        if to_create:
            cls.create_actions(elements)

    @classmethod
    def delete_actions(cls, elements):
        ActWindow = Pool().get('ir.action.act_window')
        to_delete = [x.action for x in elements if x.action]
        if to_delete:
            ActWindow.delete(to_delete)


class DashboardMockup(sequence_ordered(), ModelSQL, ModelView):
    'Shine Dashboard Mockups'
    __name__ = 'shine.dashboard.mockup'
    dashboard = fields.Many2One('shine.dashboard', 'Dashboard', required=True,
        ondelete='CASCADE')
    column1 = fields.Char('Column 1', size=1)
    column2 = fields.Char('Column 2', size=1)
    column3 = fields.Char('Column 3', size=1)
    column4 = fields.Char('Column 4', size=1)
    column5 = fields.Char('Column 5', size=1)
    column6 = fields.Char('Column 6', size=1)
    column7 = fields.Char('Column 7', size=1)
    column8 = fields.Char('Column 8', size=1)
    column9 = fields.Char('Column 9', size=1)
    column10 = fields.Char('Column 10', size=1)
    column11 = fields.Char('Column 11', size=1)
    column12 = fields.Char('Column 12', size=1)

    COLUMNS = ('column%s' % x for x in range(1, 12))

    def changed(self, column):
        value = getattr(self, column)
        if value:
            #value = value.upper()
            number = int(column.split('n')[-1])
            if value.islower():
                for c in range(number, 12 + 1):
                    setattr(self, 'column%d' % c, value)
            if value.isupper():
                for c in range(0, number + 1):
                    setattr(self, 'column%d' % c, value)

    @fields.depends(*COLUMNS)
    def on_change_column1(self):
        self.changed('column1')

    @fields.depends(*COLUMNS)
    def on_change_column2(self):
        self.changed('column2')

    @fields.depends(*COLUMNS)
    def on_change_column3(self):
        self.changed('column3')

    @fields.depends(*COLUMNS)
    def on_change_column4(self):
        self.changed('column4')

    @fields.depends(*COLUMNS)
    def on_change_column5(self):
        self.changed('column5')

    @fields.depends(*COLUMNS)
    def on_change_column6(self):
        self.changed('column6')

    @fields.depends(*COLUMNS)
    def on_change_column7(self):
        self.changed('column7')

    @fields.depends(*COLUMNS)
    def on_change_column8(self):
        self.changed('column8')

    @fields.depends(*COLUMNS)
    def on_change_column9(self):
        self.changed('column9')

    @fields.depends(*COLUMNS)
    def on_change_column10(self):
        self.changed('column10')

    @fields.depends(*COLUMNS)
    def on_change_column11(self):
        self.changed('column11')

    @fields.depends(*COLUMNS)
    def on_change_column12(self):
        self.changed('column12')
