# Copyright 2018 Xavier Jiménez <xavier.jimenez@qubiq.es>
# Copyright 2020 Jesús Ramoneda <jesus.ramoneda@qubiq.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    old_code = fields.Integer(
        string="Old Code"
    )

    """
    Function inherited to do the account_move_line checking
    when the account_move is posted
    """

    def post(self, invoice=False):
        for move in self:
            move._check_balanced(force=True)
        return super(AccountMove, self).post()

    """
    Function overrited, otherwise you can't change amounts
    when importing account_move_lines.
    """

    def _check_balanced(self, force=False):
        for s in self.filtered(lambda x: x.state != 'draft'):
            moves = s.filtered(lambda move: move.line_ids)
            if not moves or force:
                return
            # /!\ As this method is called in create / write, we can't make the
            # assumption the computed stored fields
            # are already done. Then, this query MUST NOT depend of computed
            # stored fields (e.g. balance).
            # It happens as the ORM makes the create with the 'no_recompute'
            # statement.
            self.env['account.move.line'].flush(['debit', 'credit', 'move_id'])
            self.env['account.move'].flush(['journal_id'])
            self._cr.execute('''
                SELECT line.move_id, ROUND(SUM(line.debit - line.credit),
                currency.decimal_places)
                FROM account_move_line line
                JOIN account_move move ON move.id = line.move_id
                JOIN account_journal journal ON journal.id = move.journal_id
                JOIN res_company company ON company.id = journal.company_id
                JOIN res_currency currency ON currency.id = company.currency_id
                WHERE line.move_id IN %s
                GROUP BY line.move_id, currency.decimal_places
                HAVING ROUND(SUM(line.debit - line.credit),
                currency.decimal_places) != 0.0;
            ''', [tuple(s.ids)])

            query_res = self._cr.fetchall()
            if query_res:
                ids = [res[0] for res in query_res]
                sums = [res[1] for res in query_res]
                raise UserError(
                    _("Cannot create unbalanced journal entry. Ids: %s\n\
                        Differences debit - credit: %s") % (ids, sums))
