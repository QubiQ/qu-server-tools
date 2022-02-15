# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Copyright (c) 2018 QubiQ (http://www.qubiq.es)

from odoo import models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def simple_vat_check(self, country_code, vat_number):
        return True
