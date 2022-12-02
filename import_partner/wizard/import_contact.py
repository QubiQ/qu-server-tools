# Copyright 2018 Sergi Oliva <sergi.oliva@qubiq.es>
# Copyright 2018 Xavier Jiménez <xavier.jimenez@qubiq.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from xml.dom import ValidationErr
from odoo import fields, models, exceptions, _
from odoo.exceptions import ValidationError

import base64
import csv
from io import StringIO

import logging
_logger = logging.getLogger(__name__)


class ImportContact(models.TransientModel):
    _name = 'import.contact'

    data = fields.Binary('File', required=True)
    name = fields.Char('Filename')
    delimeter = fields.Char('Delimiter', default=',',
                            help='Default delimiter ","')


    def check_all_fields(self, values):
        fields = [
            'ref',
            'parent_id',
            'company_id',
            'name',
            'type',
            'function',
            'phone',
            'mobile',
            'email',
            'lang',
            'street',
            'zip',
            'city',
            'state',
            'country',
        ]
        for field in fields:
            if field not in values:
                raise ValidationError(
                    _("Value '%s' not found!") % field
                )

    '''
        Function to update and correct some values.

        :param values: Dict with the values to import.

        :return Dict with the modified values modifieds.
    '''
    def _update_values(self, values):
        errors = []
        no_code = False
        try:
            if not values['ref']:
                no_code = True                
        except Exception as err:
            errors += [err]

        if no_code:
            raise ValidationError(_('No unique code for the contact %s') % values['name'])

        try:
            if values['company_id']:
                values['company_id'] = int(values['company_id'])
        except Exception as err:
            errors += [err]

        try:
            if values['parent_id']:
                parent_obj = self.env['res.partner'].search([
                    ('ref', '=', values['parent_id']),
                    ('parent_id', '=', False),                    
                    '|',
                    ('company_id', '=', values['company_id']),
                    ('company_id', '=', False),
                ])
                if parent_obj:
                    values['parent_id'] = parent_obj.id
                else:
                    values['parent_id'] = False
        except Exception as err:
            raise ValidationError((_("(Parent %s can not be found) ") + str(err)) % values['parent_id'])
        
        try:
            if values['zip'] and values['country'] == 'ES':
                values['zip'] = values['zip'].zfill(5)
        except Exception as err:
            errors += [err]

        return values, errors

    '''
        Function to assign not direct mapping data.

        :param values: Dict with the values to import.

        :return Dict with the correct mapping.
    '''

    def _assign_contact_data(self, values):
        contact_data = {}
        errors = []

        if values['country']:
            country_obj = self.env['res.country'].search([
                ('code', '=', values['country'])
            ])
            if country_obj:
                contact_data.update({
                    'country_id': country_obj.id,
                })
                if values['state']:
                    state = str(values['state']).capitalize()
                    state_obj = self.env['res.country.state'].search([
                        ('name', 'ilike', state),
                        ('country_id', '=', country_obj.id),
                    ])
                    if state_obj:
                        contact_data.update({
                            'state_id': state_obj.id,
                        })
                    else:
                        errors += [('%s value for state not found.' % state)]
            else:
                errors += [('%s value for country not found.' % values['country'])]
        del values['state']
        del values['country']

        return contact_data, errors

    '''
        Function to create or write the partner / supplier.

        :param values: Dict with the values to import.
    '''
    def _create_new_contact(self, values):
        total_errors = []
        values, errors = self._update_values(values)
        total_errors += errors
        contact = self.env['res.partner']
        if values['parent_id']:
            contact = self.env['res.partner'].search([
                ('ref', '=', values['ref']),
                ('parent_id', '=', values['parent_id']),
                ('company_id', '=', values['company_id'])
            ])
            fields, errors = self._assign_contact_data(values)
            total_errors += errors
            if contact:
                contact.write(values)
                _logger.info("Updating contact: %s", contact.name)
            else:
                contact = contact.create(values)
                _logger.info("Creating contact: %s", contact.name)
            contact.write(fields)
        else:
            _logger.info("Parent Partner not Found")
        
        if contact:
            result = 'correct'
            error_text = ''
            if total_errors:
                result = 'error'
                error_text = self.generate_msg_error(total_errors)
            contact.write({
                'migration_result': result,
                'migration_description_error': error_text,
            })

    '''
        Function to read the csv file and convert it to a dict.

        :return Dict with the columns and its value.
    '''
    def action_import(self):
        import wdb
        wdb.set_trace()
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
            if k != '':
                temp = k.replace(' ', '_')
                keys.append(temp)
        del reader_info[0]
        values = {}
        self.check_all_fields(keys)
        for i in range(len(reader_info)):
            # Don't read rows that start with ( or are empty
            if not (reader_info[i][0] == '' or reader_info[i][0][0] == '('
                    or reader_info[i][0][0] == ' '):
                field = reader_info[i]
                values = dict(zip(keys, field))
                self._create_new_contact(values)

        return {'type': 'ir.actions.act_window_close'}
    
    def generate_msg_error(self, errors):
        error_html = "<p><strong>MIGRATION VALIDATION FAILED:</strong></p><ul>"
        for err in errors:
            error_html += "<li>" + err + "</li>"
        error_html += "</ul>"
        return error_html
