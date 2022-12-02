# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Copyright (c) 2018 QubiQ (http://www.qubiq.es)

from odoo import models, fields, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    migration_result = fields.Selection(
        string="Migration Result",
        selection=[
            ('correct', _('Correct')),
            ('error', _('Error')),
        ]
    )
    migration_description_error = fields.Text(
        string="Migration description error"
    )
    unique_code = fields.Char(
        string="Unique Code"
    )
    unique_code_contact = fields.Char(
        string="Contact Unique Code"
    )
    migration_account_code = fields.Char(
        string="Migration account code"
    )
    migration_account_code_multicompany = fields.Text(
        string="Migration account code multicompany"
    )

    def update_partner_by_account_multicompany(self, all=False):
        for sel in self:
            if sel.migration_account_code_multicompany:
                accounts_x_companies = sel.migration_account_code_multicompany.split(';')
                for account in accounts_x_companies:
                    company, account = account.split(':')
                    domain = [
                        ('migration_account', '=', account),
                        ('company_id', '=', int(company)),
                    ]
                    if not all:
                        domain += [('partner_id', '=', False)]
                    account_move_lines = self.env['account.move.line'].sudo().search(domain)  
                    for line in account_move_lines:
                        line.sudo().write({'partner_id': sel.id})       
