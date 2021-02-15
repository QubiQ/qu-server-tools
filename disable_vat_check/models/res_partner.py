# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Copyright (c) 2018 QubiQ (http://www.qubiq.es)

from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def check_vat(self):
        return True
