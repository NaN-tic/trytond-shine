
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase


class ShineTestCase(ModuleTestCase):
    'Test Shine module'
    module = 'shine'
    extras = ['dashboard']


del ModuleTestCase
