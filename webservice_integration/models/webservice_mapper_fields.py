from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class WebserviceMapperFields(models.Model):
    _name = 'webservice.mapper.fields'
    _description = 'Webservice Mapper Fields'
    odoo_field = fields.Many2one(
        comodel_name='ir.model.fields',
        required=True,
        help="Table name or model name if the source is odoo")
    odoo_relation = fields.Char(related="odoo_field.relation")
    field_type = fields.Selection(related="odoo_field.ttype")
    source_field = fields.Char(help="Field name from the source")
    dependence_id = fields.Many2one(
        comodel_name='webservice.mapper',)
    webservice_mapper_id = fields.Many2one(
        comodel_name='webservice.mapper',
        string='Webservice Mapper',
        copy=True
    )
    state_valid = fields.Selection(
        string='Valid',
        selection=[('not_check', 'Not Checked'),
                   ('valid', 'Valid'),
                   ('not_valid', 'Not Valid')],
        default='not_check')

    unique = fields.Boolean(string='')
    map_values = fields.Char(string='Map Values',
                             help="Transform values recivied")
    create_method = fields.Selection(
        selection=[('before', 'Before'),
                   ('together', 'Together'),
                   ('after', 'After')],
        default='together', compute="_compute_create_method",
        store=True, readonly=False)
    search_operator = fields.Selection(
        selection=[('&', 'AND'), ('|', 'OR')], default="|")

    @api.depends('field_type')
    def _compute_create_method(self):
        for rec in self:
            if rec.field_type in ["one2many", "many2many"]:
                rec.create_method = 'together'

    def get_export_field_data(self):
        """Returns a list with data for export"""
        return [
            self.odoo_field.name,
            self.source_field or "",
            self.dependence_id.get_ref_code() or "",
            self.unique,
            self.map_values or "",
            self.create_method or "",
            self.search_operator or ""
        ]

    def get_company_domain(self):
        """This function returns company domain if
           the model has a company_id field"""
        self.ensure_one()
        model_obj = self.env['ir.model'].search([
                ('model', '=', self.odoo_field.relation)
            ])
        if not model_obj or not self.webservice_mapper_id.webservice_id:
            return []
        if model_obj.field_id.filtered(
             lambda o: o.name == 'company_id'):
            company_id = self.webservice_mapper_id.webservice_id.company_id
            return [("company_id", "=", company_id.id)]
        return []

    def get_field_domain(self, value):
        op = 'in' if type(value) is list else '='
        return [(self.odoo_field.name, op, value)]

    def transform_data(self, val):
        """Recive, transform and return data"""
        self.ensure_one()
        try:
            if not self.map_values:
                return val
            transfomer = eval(self.map_values)
            if transfomer:
                return transfomer.get(val, False) or val
            else:
                return val
        except Exception:
            raise UserError(_("Map values of %s are incorrect") %
                            self.odoo_field.name)
        return val

    @api.multi
    def create_dependence(self):
        rec_list = []
        for rec in self.filtered(lambda x: x.odoo_relation and not
                                 x.dependence_id):
            rec.dependence_id = rec._create_dependence()
            rec_list.append(rec.dependence_id)
        return rec_list

    def _create_dependence(self):
        """This functions create a new mapper if there are dependences
        in the current field Returns a record"""
        try:
            parent_id = self.webservice_mapper_id
            model_obj = self.env['ir.model'].search([
                ('model', '=', self.odoo_field.relation)
            ])
            mapper_obj = self.env['webservice.mapper'].search([
                ('odoo_model', '=', model_obj.id),
                ('webservice_id', '=', parent_id.webservice_id.id),
            ])
            if mapper_obj:
                mapper_obj.write({'dep_field_ids': [(4, self.id)]})
                return mapper_obj
            values = {
                'name': model_obj.name,
                'active': parent_id.active,
                'source_model': model_obj.model,
                'odoo_model': model_obj.id,
                'dep_field_ids': [(4, self.id)],
                'webservice_id': parent_id.webservice_id.id,
                'update': parent_id.update,
                'create_active': parent_id.create_active,
            }
            return mapper_obj.create(values)
        except Exception as e:
            raise UserError("Error when creating dependence mappers:\n %s"
                            % str(e))

    def search_record(self, value, many2many):
        """Search relation by name or by old id
        return the record or False"""
        self.ensure_one()
        model_id = self.env['ir.model'].search([
            ('model', '=', self.odoo_relation)
        ])
        model_obj = self.env[self.odoo_relation]
        field = self.env['ir.model.fields'].search_count([
            ('model_id', '=', model_id.id),
            ('name', '=', 'x_old_id')
            ])
        if field:
            if many2many:
                domain = [('x_old_id', 'in', value)]
            else:
                domain = [('x_old_id', '=', value[0])]
            rec = model_obj.search(domain)
            if rec and many2many:
                return rec
            if len(rec) == 1:
                return rec
        if many2many:
            return False
        field = self.env['ir.model.fields'].search_count([
            ('model_id', '=', model_id.id),
            ('name', '=', 'name')
            ])
        if field:

            if value[1][-1] == ' ':
                value[1] = value[1][:-1]
            value[1] = self.transform_data(value[1])
            rec = model_obj.search(
                [('name', '=', value[1])]
            )
            if len(rec) == 1:
                return rec

    def open_mapper(self):
        self.ensure_one()
        if not self.dependence_id:
            return
        action = self.env.ref(
            'webservice_integration.webservice_mapper_action_form')
        action['res_id'] = self.dependence_id.id
        return action
