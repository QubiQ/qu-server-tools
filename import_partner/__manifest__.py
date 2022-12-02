# Copyright 2018 Sergi Oliva <sergi.oliva@qubiq.es>
# Copyright 2018 Xavier Jiménez <xavier.jimenez@qubiq.es>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Import Partner",
    "summary": "Import Partner",
    "version": "15.0.1.0.0",
    "category": "Partner",
    "website": "https://www.qubiq.es",
    "author": "QubiQ",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "external_dependencies": {
        "python": [],
        "bin": [],
    },
    "depends": [
        "base",
        "sale",
        "account_payment_mode",
        "l10n_es_partner",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner.xml",
        "wizard/import_partner.xml",
        "wizard/import_contact.xml",
    ],
}
