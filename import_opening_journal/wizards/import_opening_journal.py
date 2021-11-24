# Copyright 2018 Xavier Jiménez <xavier.jimenez@qubiq.es>
# Copyright 2018 Sergi Oliva <sergi.oliva@qubiq.es>
# Copyright 2020 Jesús Ramoneda <jesus.ramoneda@qubiq.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, exceptions, _

import base64
import csv
from io import StringIO
from datetime import datetime

import logging
_logger = logging.getLogger(__name__)


class ImportOpeningJournal(models.TransientModel):
    _name = 'import.opening.journal'

    data = fields.Binary(string='File', required=True)
    name = fields.Char(string='Filename')
    delimeter = fields.Char(
        string='Delimiter',
        default=',',
        help='Default delimiter ","',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True
    )

    '''
        Function to update and correct some values.

        :param values: Dict with the values to import.

        :return Dict with the modified values modifieds.
    '''
    def _update_values(self, values):
        if values['date']:
            values['date'] = values['date'].replace(' ', '')

        if values['debit']:
            values['debit'] = values['debit'].replace('.', '')
            values['debit'] = values['debit'].replace(',', '.')

        if values['credit']:
            values['credit'] = values['credit'].replace('.', '')
            values['credit'] = values['credit'].replace(',', '.')

        values.update({
            'debit': float(values['debit']) if values['debit'] else 0.00,
            'credit': float(values['credit']) if values['credit'] else 0.00,
        })
        if values['debit'] < 0:
            values['credit'] = abs(values['debit'])
            values['debit'] = 0.00

        if values['credit'] < 0:
            values['debit'] = abs(values['credit'])
            values['credit'] = 0.00

        if values['account']:
            if not values['account'][:2] in ('40', '41', '43'):
                first = False
                if len(values['account']) < 6:
                    values['account'] =\
                     values['account'].ljust(6, '0')
                else:
                    max_len = len(values['account'])
                    for digit in range(0, max_len):
                        if values['account'][digit] == '0':
                            if first:
                                last = 6 - first
                                if last == 0:
                                    new_code = values['account'][:digit-1]
                                else:
                                    new_code =\
                                     values['account'][:digit-1] + \
                                     values['account'][-last:]
                                values['account'] = new_code
                                break
                            first = digit
                        else:
                            first = False
            else:
                if values['account'][:2] == '40':
                    values['account'] = '400000'
                if values['account'][:2] == '41':
                    values['account'] = '410000'
                if values['account'][:2] == '43':
                    values['account'] = '430000'

        return values

    def _assign_move_line_data(self, values):
        # Search for the account
        if values['account']:
            account_obj = self.env['account.account'].search([
                ('code', '=', values['account']),
                ('company_id', '=', self.company_id.id),
            ])
            if account_obj:
                values.update({
                    'account_id': account_obj.id,
                })
        del values['account']

        if values['tax']:
            tax_obj = self.env['account.tax'].search([
                ('description', '=', values['tax'])
            ])
            if tax_obj:
                values.update({
                    'tax_ids': [(6, 0, tax_obj.ids)]
                })
        del values['tax']

        return values

    '''
        Function to create the opening journal lines.

        :param values: Dict with the values to import.
    '''
    def _create_new_opening_journal(self, values, i):
        values = self._assign_move_line_data(values)
        acc_move_obj = self.env['account.move'].search([
            ('old_code', '=', values['move_id'])
        ])

        if not acc_move_obj:
            journal_obj = self.env['account.journal'].search([
                ('code', '=', 'MISC')
            ])
            acc_move_obj = acc_move_obj.sudo().create({
                'journal_id': journal_obj.id,
                'old_code': values['move_id'],
                'ref': values['move_name'],
                'date': datetime.strptime(values['date'], "%d-%m-%y"),
                # 'name': values['move_name']
            })
        # acc_move_obj.name = values['move_name']
        del values['move_id']
        del values['date']
        del values['move_name']

        values['move_id'] = acc_move_obj.id
        op_ml_obj = self.env['account.move.line']

        _logger.info("Creating line for %d", i)
        op_ml_obj = op_ml_obj.sudo().create(values)

    def update_accounts(self, values):
        move_line = self.env['account.move.line']
        if values['account']:
            first = False
            if len(values['account']) < 6:
                values['account'] =\
                 values['account'].ljust(6, '0')
            else:
                max_len = len(values['account'])
                for digit in range(0, max_len):
                    if values['account'][digit] == '0':
                        if first:
                            last = 6 - first
                            if last == 0:
                                new_code = values['account'][:digit-1]
                            else:
                                new_code =\
                                 values['account'][:digit-1] + \
                                 values['account'][-last:]
                            values['account'] = new_code
                            break
                        first = digit
                    else:
                        first = False
        if values['account'][:2] == '40':
            account_40 = self.env['account.account'].search([
                ('code', '=', '400000'),
                ('company_id', '=', self.company_id.id),
            ])
            move_line = self.env['account.move.line'].search([
                ('name', '=', values['name']),
                ('move_id.old_code', '=', values['move_id']),
                ('account_id', '=', account_40.id),
            ], limit=1)
        if values['account'][:2] == '41':
            account_41 = self.env['account.account'].search([
                ('code', '=', '410000'),
                ('company_id', '=', self.company_id.id),
            ])
            move_line = self.env['account.move.line'].search([
                ('name', '=', values['name']),
                ('move_id.old_code', '=', values['move_id']),
                ('account_id', '=', account_41.id),
            ], limit=1)
        if values['account'][:2] == '43':
            account_43 = self.env['account.account'].search([
                ('code', '=', '430000'),
                ('company_id', '=', self.company_id.id),
            ])
            move_line = self.env['account.move.line'].search([
                ('name', '=', values['name']),
                ('move_id.old_code', '=', values['move_id']),
                ('account_id', '=', account_43.id),
            ], limit=1)

        if move_line:
            account_obj = self.env['account.account'].search([
                ('code', '=', values['account']),
                ('company_id', '=', self.company_id.id),
            ])
            if account_obj:
                move_line.write({
                    'account_id': account_obj.id,
                })
                _logger.info("Updating line: %s", move_line.name)
            else:
                _logger.info("Account not found: %s",  values['account'])
    '''
        Function to read the csv file and convert it to a dict.

        :return Dict with the columns and its value.
    '''
    def action_import(self):
        """Load Inventory data from the CSV file."""
        if not self.data:
            raise exceptions.Warning(_("You need to select a file!"))
        # Decode the file data
        data = base64.b64decode(self.data).decode('utf-8')
        file_input = StringIO(data)
        file_input.seek(0)

        reader_info = []
        if self.delimeter:
            delimeter = str(self.delimeter)
        else:
            delimeter = ','
        reader = csv.reader(file_input, delimiter=delimeter,
                            lineterminator='\r\n')
        try:
            reader_info.extend(reader)
        except Exception:
            raise exceptions.Warning(_("Not a valid file!"))
        keys = reader_info[0]

        # Get column names
        keys_init = reader_info[0]
        keys = []
        for k in keys_init:
            temp = k.replace(' ', '_')
            keys.append(temp)

        del reader_info[0]
        values = {}

        for i in range(len(reader_info)):
            # Don't read rows that start with ( , ' ' or are empty
            if not (reader_info[i][0] == '' or reader_info[i][0][0] == '('
                    or reader_info[i][0][0] == ' '):
                field = reader_info[i]
                values = dict(zip(keys, field))
                if len(values) == 3:
                    self.update_accounts(values)
                else:
                    new_values = self._update_values(values)
                    self._create_new_opening_journal(new_values, i+2)

        return {'type': 'ir.actions.act_window_close'}
