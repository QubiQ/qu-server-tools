# Copyright 2018 Xavier Jiménez <xavier.jimenez@qubiq.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models, api
import logging
_logger = logging.getLogger(__name__)


class AcquirerRedsys(models.Model):
    _inherit = 'payment.acquirer'

    @api.multi
    def redsys_form_generate_values(self, values):
        tx_obj = self.env['payment.transaction'].search([
            ('reference', '=', values['reference'])
        ])
        if tx_obj:
            reference = self.env['ir.sequence'].next_by_code(
                'payment.transaction')
            tx_obj.write({'reference': reference})
            values.update({'reference': reference})

        res = super(AcquirerRedsys, self).redsys_form_generate_values(values)
        return res


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _confirm_so(self):
        if self.state == 'pending' and self.sale_order_id.state == 'draft' and self.acquirer_id.provider == 'redsys':
            _logger.info('<%s> transaction not processed for order %s (ID %s)', self.acquirer_id.provider, self.sale_order_id.name, self.sale_order_id.id)
            return False
        else:
            return super(PaymentTransaction, self)._confirm_so()
