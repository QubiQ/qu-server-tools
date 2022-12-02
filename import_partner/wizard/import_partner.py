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


class ImportPartner(models.TransientModel):
    _name = 'import.partner'

    data = fields.Binary('File', required=True)
    name = fields.Char('Filename')
    delimeter = fields.Char('Delimiter', default=',',
                            help='Default delimiter ","')

    def check_all_fields(self, values):
        fields = [
            'ref',
            'supplier',
            'customer',
            'name',
            'comercial',
            'is_company',            
            'company_id',
            'street',
            'zip',
            'city',
            'state',
            'country',
            'lang',
            'categories',
            'phone',
            'mobile',
            'email',
            'website',
            'vat',
            'payment_mode',
            'payment_term',
            'iban',
            'fiscal_position',
            'comment',
        ]
        for field in fields:
            if field not in values:
                raise ValidationError(
                    _("Value '%s' not found!") % field
                )

    def _update_values(self, values):
        errors = []
        try:
            if values['zip'] and values['country'] == 'ES':
                values['zip'] = values['zip'].zfill(5)
        except Exception as err:
            errors += [err]
        
        try:
            if values['company_id']:
                values['company_id'] = int(values['company_id'])
        except Exception as err:
            errors += [err]
        
        try:
            property_values = {
                'payment_term': values['payment_term'],
                'payment_mode': values['payment_mode'],
                'fiscal_position': values['fiscal_position']
            }
            del values['payment_term']
            del values['payment_mode']
            del values['fiscal_position']
        except Exception as err:
            errors += [err]

        return values, property_values, errors

    '''
        Function to assign not direct mapping data.

        :param values: Dict with the values to import.

        :return Dict with the correct mapping.
    '''

    def _assign_partner_data(self, values):
        bank_info = {}
        partner_info = {}
        errors = []

        if values['country']:
            country_obj = self.env['res.country'].search([
                ('code', '=', values['country'])
            ])
            if country_obj:
                partner_info.update({
                    'country_id': country_obj.id,
                })
                if values['state']:
                    state = str(values['state']).capitalize()
                    state_obj = self.env['res.country.state'].search([
                        ('name', 'ilike', state),
                        ('country_id', '=', country_obj.id),
                    ])
                    if state_obj:
                        partner_info.update({
                            'state_id': state_obj.id,
                        })
                    else:
                        errors += [('%s value for state not found.' % state)]
            else:
                errors += [('%s value for country not found.' % values['country'])]
        del values['state']
        del values['country']

        if values['categories']:
            category_ids = self.env['res.partner.category']
            categories = values['categories'].split(';') # Quizas ('"')
            for categ in categories:
                category_obj = self.env['res.partner.category'].search([
                    ('name', '=', categ)
                ])
                if not category_obj:
                    category_obj = self.env['res.partner.category'].create({
                        'name': categ,
                    })
                category_ids += category_obj
            if category_ids:
                partner_info.update({
                    'category_id': [(6, 0, category_ids.ids)],
                })            
        del values['categories']

        # Create and assign bank account
        if values['iban']:
            values['iban'] = values['iban'].replace(' ', '')
            bank_acc_obj = self.env['res.partner.bank'].search([(
                'acc_number', '=', values['iban'])
            ])
            if not bank_acc_obj:
                bank_values = {}
                bank_code = values['iban'][4:8]
                bank_obj = self.env['res.bank'].search([(
                    'code', '=', bank_code)])
                bank_values = {
                    'acc_number': values['iban'],
                }
                if bank_obj:
                    bank_values.update({
                        'bank_id': bank_obj.id,
                    })
                bank_info = bank_values

            else:
                partner_info.update({
                    'bank_ids': [(6, 0, bank_acc_obj.ids)],
                })
        del values['iban']

        return partner_info, bank_info, errors

    '''
        Function to create or write the partner / supplier.

        :param values: Dict with the values to import.
    '''
    def _create_new_partner(self, values):
        total_errors = []
        is_customer = False
        is_supplier = False
        if values['supplier']:
            if values['supplier'] == 'True':
                is_supplier = True
            if values['customer'] == 'True':
                is_customer = True
        del values['supplier']
        del values['customer']

        values, properties, errors = self._update_values(values)
        total_errors += errors
        current_partner = self.env['res.partner'].search([
            ('ref', '=', values['ref']),
            ('parent_id', '=', False),
            '|',
            ('company_id', '=', values['company_id']),
            ('company_id', '=', False),
        ])

        fields, bank_info, errors = self._assign_partner_data(values)
        total_errors += errors
        if current_partner:
            current_partner.sudo().write(values)
            _logger.info("Updating current_partner: %s", current_partner.name)
        else:
            current_partner = current_partner.sudo().create(values)
            _logger.info("Creating partner: %s", current_partner.name)

        current_partner.sudo().write(fields)
        self._create_properties(
            current_partner,
            properties,
            is_supplier,
            is_customer,
        )
        if bank_info:
            if current_partner.company_id:
                cur_company = current_partner.company_id.id
            else:
                cur_company = False
            bank_info.update({
                'partner_id': current_partner.id,
                'company_id': cur_company,
            })
            bank_obj = self.sudo().env[
                'res.partner.bank'].create(bank_info)
            current_partner.write({
                'bank_ids': [(6, 0, [bank_obj.id])]
            })

        result = 'correct'
        error_text = ''
        if total_errors:
            result = 'error'
            error_text = self.generate_msg_error(total_errors)
        current_partner.write({
            'migration_result': result,
            'migration_description_error': error_text,
        })

    def _create_properties(self, partner, property_values, is_supplier, is_customer):
        res_id = 'res.partner,' + str(partner.id)
        if is_customer == True:
            if property_values['payment_term']:
                cust_pt = self.env['account.payment.term'].search([
                    ('name', '=', property_values['payment_term']),
                ])
                if cust_pt:
                    field_name = 'property_payment_term_id'
                    fields_obj = self.env['ir.model.fields'].search([
                        ('model', '=', 'res.partner'),
                        ('name', '=', field_name),
                    ])
                    property_term_cust_pt = self.env['ir.property'].search([
                            ('res_id', '=', res_id),
                            ('fields_id', '=', fields_obj.id),
                            ('company_id', '=', partner.company_id.id)
                        ])
                    if not property_term_cust_pt:
                        self.env['ir.property'].create({
                            'name': field_name,
                            'res_id': res_id,
                            'fields_id': fields_obj.id,
                            'company_id': partner.company_id.id,
                            'value_reference': 'account.payment.term,' +
                                                str(cust_pt.id),
                        })
                    if property_term_cust_pt:
                        property_term_cust_pt.write({
                            'name': field_name,
                            'res_id': res_id,
                            'fields_id': fields_obj.id,
                            'company_id': partner.company_id.id,
                            'value_reference': 'account.payment.term,' +
                                                str(cust_pt.id),
                        })

            if property_values['payment_mode']:
                cust_pm = self.env['account.payment.mode'].search([
                    ('name', '=', property_values['payment_mode']),
                    ('company_id', '=', partner.company_id.id),
                ])
                if cust_pm:
                    field_name = 'customer_payment_mode_id'
                    fields_obj = self.env['ir.model.fields'].search([
                        ('model', '=', 'res.partner'),
                        ('name', '=', field_name),
                    ])
                    property_mode_cust_pm = self.env['ir.property'].search([
                            ('res_id', '=', res_id),
                            ('fields_id', '=', fields_obj.id),
                            ('company_id', '=', partner.company_id.id)
                        ])
                    if not property_mode_cust_pm:
                        self.env['ir.property'].create({
                            'name': field_name,
                            'res_id': res_id,
                            'fields_id': fields_obj.id,
                            'company_id': partner.company_id.id,
                            'value_reference': 'account.payment.mode,' +
                                                str(cust_pm.id),
                        })
                    if property_mode_cust_pm:
                        property_mode_cust_pm.write({
                            'name': field_name,
                            'res_id': res_id,
                            'fields_id': fields_obj.id,
                            'company_id': partner.company_id.id,
                            'value_reference': 'account.payment.mode,' +
                                                str(cust_pm.id),
                        })

        if is_supplier == True:
            if property_values['payment_term']:
                sup_pt = self.env['account.payment.term'].search([
                    ('name', '=', property_values['payment_term']),
                ])
                if sup_pt:
                    field_name = 'property_supplier_payment_term_id'
                    fields_obj = self.env['ir.model.fields'].search([
                        ('model', '=', 'res.partner'),
                        ('name', '=', field_name),
                    ])
                    property_term = self.env['ir.property'].search([
                            ('res_id', '=', res_id),
                            ('fields_id', '=', fields_obj.id),
                            ('company_id', '=', partner.company_id.id)
                        ])
                    if not property_term:
                        self.env['ir.property'].create({
                            'name': field_name,
                            'res_id': res_id,
                            'fields_id': fields_obj.id,
                            'company_id': partner.company_id.id,
                            'value_reference': 'account.payment.term,' +
                                                str(sup_pt.id),
                        })
                    if property_term:
                        property_term.write({
                            'name': field_name,
                            'res_id': res_id,
                            'fields_id': fields_obj.id,
                            'company_id': partner.company_id.id,
                            'value_reference': 'account.payment.term,' +
                                                str(sup_pt.id),
                        })

            if property_values['payment_mode']:
                sup_pm = self.env['account.payment.mode'].search([
                    ('name', '=', property_values['payment_mode']),
                    ('company_id', '=', partner.company_id.id),
                ])
                if sup_pm:
                    field_name = 'supplier_payment_mode_id'
                    fields_obj = self.env['ir.model.fields'].search([
                        ('model', '=', 'res.partner'),
                        ('name', '=', field_name),
                    ])
                    property_mode = self.env['ir.property'].search([
                            ('res_id', '=', res_id),
                            ('fields_id', '=', fields_obj.id),
                            ('company_id', '=', partner.company_id.id)
                        ])
                    if not property_mode:
                        self.env['ir.property'].create({
                            'name': field_name,
                            'res_id': res_id,
                            'fields_id': fields_obj.id,
                            'company_id': partner.company_id.id,
                            'value_reference': 'account.payment.mode,' +
                                                str(sup_pm.id),
                        })
                    if property_mode:
                        property_mode.write({
                            'name': field_name,
                            'res_id': res_id,
                            'fields_id': fields_obj.id,
                            'company_id': partner.company_id.id,
                            'value_reference': 'account.payment.mode,' +
                                                str(sup_pm.id),
                        })

        if property_values['fiscal_position']:
            fp = self.env['account.fiscal.position'].search([
                ('name', '=', property_values['fiscal_position']),
                ('company_id', '=', partner.company_id.id),
            ])
            if fp:
                field_name = 'property_account_position_id'
                fields_obj = self.env['ir.model.fields'].search([
                    ('model', '=', 'res.partner'),
                    ('name', '=', field_name),
                ])
                property_fp = self.env['ir.property'].search([
                        ('res_id', '=', res_id),
                        ('fields_id', '=', fields_obj.id),
                        ('company_id', '=', partner.company_id.id)
                    ])
                if not property_fp:
                    self.env['ir.property'].create({
                        'name': field_name,
                        'res_id': res_id,
                        'fields_id': fields_obj.id,
                        'company_id': partner.company_id.id,
                        'value_reference': 'account.fiscal.position,' +
                                            str(fp.id),
                    })
                if property_fp:
                    property_fp.write({
                        'name': field_name,
                        'res_id': res_id,
                        'fields_id': fields_obj.id,
                        'company_id': partner.company_id.id,
                        'value_reference': 'account.fiscal.position,' +
                                            str(fp.id),
                    })

    def generate_msg_error(self, errors):
        error_html = "<p><strong>MIGRATION VALIDATION FAILED:</strong></p><ul>"
        for err in errors:
            error_html += "<li>" + err + "</li>"
        error_html += "</ul>"
        return error_html

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
                self._create_new_partner(values)

        return {'type': 'ir.actions.act_window_close'}
