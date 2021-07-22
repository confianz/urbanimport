from . import models
from . import controllers

from odoo import api, SUPERUSER_ID


@api.model
def _create_missing_journal_braintree(cr, registry):
    '''Create the Braintree journal for active acquirers.'''
    env = api.Environment(cr, SUPERUSER_ID, {})
    company = env.company
    acquirer = env['payment.acquirer'].search(
        [('provider', '=', 'braintree'), ('journal_id', '=', False), ('company_id', '=', company.id)])

    journals = env['account.journal']

    if not acquirer.journal_id:
        acquirer.journal_id = env['account.journal'].create(acquirer._prepare_account_journal_vals())
        journals += acquirer.journal_id
    return journals
