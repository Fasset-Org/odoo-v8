import time
from openerp.osv import osv
from openerp.tools.translate import _
from openerp.report import report_sxw
from openerp.addons.account.report import common_report_header
from openerp import SUPERUSER_ID


class partner_ledger_rep(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(partner_ledger_rep, self).__init__(cr, uid, name, context=context)
        self.init_bal_sum = 0.0
        self.amount_currency = {}
        self.localcontext.update({
            'time': time,
            'lines1': self.lines1,
            'lines2': self.lines2,
            'sum_debit_partner': self._sum_debit_partner,
            'sum_credit_partner': self._sum_credit_partner,
            'get_currency': self._get_currency,
            'get_start_period': self.get_start_period,
            'get_end_period': self.get_end_period,
            'get_account': self._get_account,
            'get_filter': self._get_filter,
            'get_start_date': self._get_start_date,
            'get_end_date': self._get_end_date,
            'get_fiscalyear': self._get_fiscalyear,
            'get_journal': self._get_journal,
            'get_partners':self._get_partners,
            'get_intial_balance':self._get_intial_balance,
            'display_initial_balance':self._display_initial_balance,
            'display_currency':self._display_currency,
            'get_target_move': self._get_target_move,
            'amount_currency': self.amount_currency,
            'get_ana_account':self.get_ana_account
        })
        
    def get_ana_account(self,partner,form):
        ana_lst=[]
        acc_ser = self.pool.get('account.move.line').search(self.cr,self.uid,[('partner_id','=',partner.id)])
        if acc_ser:
            acc_brw = self.pool.get('account.move.line').browse(self.cr,self.uid,acc_ser)
            if acc_brw:
                for ac_br in acc_brw: 
                    if ac_br.analytic_account_id not in ana_lst:
                        if ac_br.analytic_account_id:
                            ana_lst.append(ac_br.analytic_account_id)
        return  ana_lst
        
    def _get_company(self, data):
        if data.get('form', False) and data['form'].get('chart_account_id', False):
            return self.pool.get('account.account').browse(self.cr, self.uid, data['form']['chart_account_id']).company_id.name
        return ''

    def _get_journal(self, data):
        codes = []
        if data.get('form', False) and data['form'].get('journal_ids', False):
            self.cr.execute('select code from account_journal where id IN %s',(tuple(data['form']['journal_ids']),))
            codes = [x for x, in self.cr.fetchall()]
        return codes

    
    
    def _get_currency(self, data):
        if data.get('form', False) and data['form'].get('chart_account_id', False):
            return self.pool.get('account.account').browse(self.cr, self.uid, data['form']['chart_account_id']).company_id.currency_id.symbol
        return ''
        
    def _get_filter(self, data):
        if data['form']['filter'] == 'unreconciled':
            return _('Unreconciled Entries')
        return super(partner_ledger_rep, self)._get_filter(data)

    def set_context(self, objects, data, ids, report_type=None):
        obj_move = self.pool.get('account.move.line')
        obj_partner = self.pool.get('res.partner')
        self.query = obj_move._query_get(self.cr, self.uid, obj='l', context=data['form'].get('used_context', {}))
        ctx2 = data['form'].get('used_context',{}).copy()
        self.initial_balance = data['form'].get('initial_balance', True)
        self.partner =data['form'].get('partner')
        if self.initial_balance:
            ctx2.update({'initial_bal': True})
        self.init_query = obj_move._query_get(self.cr, self.uid, obj='l', context=ctx2)
        self.reconcil = True
        if data['form']['filter'] == 'unreconciled':
            self.reconcil = False
        self.result_selection = data['form'].get('result_selection', 'customer')
        if data['form'].get('amount_currency'):
            self.amount_currency['currency'] = True
        else:
            self.amount_currency.pop('currency', False)
        self.target_move = data['form'].get('target_move', 'all')
        PARTNER_REQUEST = ''
        move_state = ['draft','posted']
        if self.target_move == 'posted':
            move_state = ['posted']
        if self.result_selection == 'supplier':
            self.ACCOUNT_TYPE = ['payable']
        elif self.result_selection == 'customer':
            self.ACCOUNT_TYPE = ['receivable']
        else:
            self.ACCOUNT_TYPE = ['payable','receivable']

        self.cr.execute(
            "SELECT a.id " \
            "FROM account_account a " \
            "LEFT JOIN account_account_type t " \
                "ON (a.type=t.code) " \
                'WHERE a.type IN %s' \
                "AND a.active", (tuple(self.ACCOUNT_TYPE), ))
        self.account_ids = [a for (a,) in self.cr.fetchall()]
        params = [tuple(move_state), tuple(self.account_ids)]
        #if we print from the partners, add a clause on active_ids
        if (data['model'] == 'res.partner') and ids:
            PARTNER_REQUEST =  "AND l.partner_id IN %s"
            params += [tuple(ids)]
        reconcile = "" if self.reconcil else "AND l.reconcile_id IS NULL "
        self.cr.execute(
                "SELECT DISTINCT l.partner_id " \
                "FROM account_move_line AS l, account_account AS account, " \
                " account_move AS am " \
                "WHERE l.partner_id IS NOT NULL " \
                    "AND l.account_id = account.id " \
                    "AND am.id = l.move_id " \
                    "AND am.state IN %s"
                    "AND " + self.query +" " \
                    "AND l.account_id IN %s " \
                    " " + PARTNER_REQUEST + " " \
                    "AND account.active " + reconcile + " ", params)
        self.partner_ids = [res['partner_id'] for res in self.cr.dictfetchall()]
        objects = obj_partner.browse(self.cr, SUPERUSER_ID, self.partner_ids)
        objects = sorted(objects, key=lambda x: (x.ref, x.name))
        return super(partner_ledger_rep, self).set_context(objects, data, self.partner_ids, report_type)


    def _get_intial_balance(self, partner):
        move_state = ['draft','posted']
        if self.target_move == 'posted':
            move_state = ['posted']
        if self.reconcil:
            RECONCILE_TAG = " "
        else:
            RECONCILE_TAG = "AND l.reconcile_id IS NULL"
        self.cr.execute(
            "SELECT COALESCE(SUM(l.debit),0.0), COALESCE(SUM(l.credit),0.0), COALESCE(sum(debit-credit), 0.0) " \
            "FROM account_move_line AS l,  " \
            "account_move AS m "
            "WHERE l.partner_id = %s " \
            "AND m.id = l.move_id " \
            "AND m.state IN %s "
            "AND account_id IN %s" \
            " " + RECONCILE_TAG + " "\
            "AND " + self.init_query + "  ",
            (partner.id, tuple(move_state), tuple(self.account_ids)))
        res = self.cr.fetchall()
        self.init_bal_sum = res[0][2]
        return res

    def _sum_debit_partner(self, partner):
        move_state = ['draft','posted']
        if self.target_move == 'posted':
            move_state = ['posted']

        result_tmp = 0.0
        result_init = 0.0
        if self.reconcil:
            RECONCILE_TAG = " "
        else:
            RECONCILE_TAG = "AND reconcile_id IS NULL"
        if self.initial_balance:
            self.cr.execute(
                    "SELECT sum(debit) " \
                    "FROM account_move_line AS l, " \
                    "account_move AS m "
                    "WHERE l.partner_id = %s" \
                        "AND m.id = l.move_id " \
                        "AND m.state IN %s "
                        "AND account_id IN %s" \
                        " " + RECONCILE_TAG + " " \
                        "AND " + self.init_query + " ",
                    (partner.id, tuple(move_state), tuple(self.account_ids)))
            contemp = self.cr.fetchone()
            if contemp != None:
                result_init = contemp[0] or 0.0
            else:
                result_init = result_tmp + 0.0

        self.cr.execute(
                "SELECT sum(debit) " \
                "FROM account_move_line AS l, " \
                "account_move AS m "
                "WHERE l.partner_id = %s " \
                    "AND m.id = l.move_id " \
                    "AND m.state IN %s "
                    "AND account_id IN %s" \
                    " " + RECONCILE_TAG + " " \
                    "AND " + self.query + " ",
                (partner.id, tuple(move_state), tuple(self.account_ids),))

        contemp = self.cr.fetchone()
        if contemp != None:
            result_tmp = contemp[0] or 0.0
        else:
            result_tmp = result_tmp + 0.0

        return result_tmp  + result_init

    def _sum_credit_partner(self, partner):
        move_state = ['draft','posted']
        if self.target_move == 'posted':
            move_state = ['posted']

        result_tmp = 0.0
        result_init = 0.0
        if self.reconcil:
            RECONCILE_TAG = " "
        else:
            RECONCILE_TAG = "AND reconcile_id IS NULL"
        if self.initial_balance:
            self.cr.execute(
                    "SELECT sum(credit) " \
                    "FROM account_move_line AS l, " \
                    "account_move AS m  "
                    "WHERE l.partner_id = %s" \
                        "AND m.id = l.move_id " \
                        "AND m.state IN %s "
                        "AND account_id IN %s" \
                        " " + RECONCILE_TAG + " " \
                        "AND " + self.init_query + " ",
                    (partner.id, tuple(move_state), tuple(self.account_ids)))
            contemp = self.cr.fetchone()
            if contemp != None:
                result_init = contemp[0] or 0.0
            else:
                result_init = result_tmp + 0.0

        self.cr.execute(
                "SELECT sum(credit) " \
                "FROM account_move_line AS l, " \
                "account_move AS m "
                "WHERE l.partner_id=%s " \
                    "AND m.id = l.move_id " \
                    "AND m.state IN %s "
                    "AND account_id IN %s" \
                    " " + RECONCILE_TAG + " " \
                    "AND " + self.query + " ",
                (partner.id, tuple(move_state), tuple(self.account_ids),))

        contemp = self.cr.fetchone()
        if contemp != None:
            result_tmp = contemp[0] or 0.0
        else:
            result_tmp = result_tmp + 0.0
        return result_tmp  + result_init

    
    
    def _get_partners(self):
        # TODO: deprecated, to remove in trunk
        if self.result_selection == 'customer':
            return _('Receivable Accounts')
        elif self.result_selection == 'supplier':
            return _('Payable Accounts')
        elif self.result_selection == 'customer_supplier':
            return _('Receivable and Payable Accounts')
        return ''

    def _sum_currency_amount_account(self, account, form):
        self._set_get_account_currency_code(account.id)
        self.cr.execute("SELECT sum(aml.amount_currency) FROM account_move_line as aml,res_currency as rc WHERE aml.currency_id = rc.id AND aml.account_id= %s ", (account.id,))
        total = self.cr.fetchone()
        if self.account_currency:
            return_field = str(total[0]) + self.account_currency
            return return_field
        else:
            currency_total = self.tot_currency = 0.0
            return currency_total

    def _display_initial_balance(self, data):
        if self.initial_balance:
            return True
        return False

    def _display_currency(self, data):
        if self.amount_currency:
            return True
        return False    
        
        
    def _get_account(self, data):
        if data.get('form', False) and data['form'].get('chart_account_id', False):
            return self.pool.get('account.account').browse(self.cr, self.uid, data['form']['chart_account_id']).name
        return ''

    def _get_sortby(self, data):
        raise (_('Error!'), _('Not implemented.'))

#     def _get_filter(self, data):
#         if data.get('form', False) and data['form'].get('filter', False):
#             if data['form']['filter'] == 'filter_date':
#                 return self._translate('Date')
#             elif data['form']['filter'] == 'filter_period':
#                 return self._translate('Periods')
#         return self._translate('No Filters')
    
    
    def lines1(self, partner,data):
        move_state = ['draft','posted']
        if self.target_move == 'posted':
            move_state = ['posted']

        full_account = []
        if self.reconcil:
            RECONCILE_TAG = " "
        else:
            RECONCILE_TAG = "AND l.reconcile_id IS NULL"
        self.cr.execute(
            "SELECT l.id, l.date, j.code, acc.code as a_code, acc.name as a_name, l.ref, m.name as move_name, l.name, l.debit, l.credit, l.amount_currency,l.currency_id, c.symbol AS currency_code " \
            "FROM account_move_line l " \
            "LEFT JOIN account_journal j " \
                "ON (l.journal_id = j.id) " \
            "LEFT JOIN account_account acc " \
                "ON (l.account_id = acc.id) " \
            "LEFT JOIN res_currency c ON (l.currency_id=c.id)" \
            "LEFT JOIN account_move m ON (m.id=l.move_id)" \
            "WHERE l.partner_id = %s " \
                "AND l.account_id IN %s AND " + self.query +" " \
                "AND m.state IN %s " \
                " " + RECONCILE_TAG + " "\
                "ORDER BY l.date",
                (partner.id, tuple(self.account_ids), tuple(move_state)))
        res = self.cr.dictfetchall()
        res1=[]
        if data['form']['jvtype'] == False:
            res1=res
        rid=[]
        
        if data['form']['jvtype'] == 'mandatory':
            for r in res:
                rid.append(r['id'])
            module_fields_ids = self.pool.get('account.move.line').search(self.cr, self.uid, [('id', 'in', rid), ('name', 'like', 'Mandatory')])
            for r1 in res:
                for mv_id in module_fields_ids:    
                    if mv_id == r['id']:
                        res1.append(r)
        if data['form']['jvtype'] == 'discretionary':
            for r in res:
                rid.append(r['id'])
            module_fields_ids = self.pool.get('account.move.line').search(self.cr, self.uid, [('id', 'in', rid), ('name', 'like', 'Tranche')])
            
            for r1 in res:
                for mv_id in module_fields_ids:    
                    if mv_id == r1['id']:
                        res1.append(r1)
        sum = 0.0
        if self.initial_balance:
            sum = self.init_bal_sum
        for r in res1:
            sum += r['debit'] - r['credit']
            r['progress'] = sum
            full_account.append(r)
        return full_account
        

    
    def lines2(self, partner,ana,data):
            
            
            
            
            
            move_state = ['draft','posted']
            if self.target_move == 'posted':
                move_state = ['posted']
    
            full_account = []
            if self.reconcil:
                RECONCILE_TAG = " "
            else:
                RECONCILE_TAG = "AND l.reconcile_id IS NULL"
            if self.partner:
                self.cr.execute(
                    "SELECT l.id, l.date, j.code, acc.code as a_code, acc.name as a_name, l.ref, m.name as move_name, l.name, l.debit, l.credit, l.amount_currency,l.currency_id, c.symbol AS currency_code " \
                    "FROM account_move_line l " \
                    "LEFT JOIN account_journal j " \
                        "ON (l.journal_id = j.id) " \
                    "LEFT JOIN account_account acc " \
                        "ON (l.account_id = acc.id) " \
                    "LEFT JOIN res_currency c ON (l.currency_id=c.id)" \
                    "LEFT JOIN account_move m ON (m.id=l.move_id)" \
                    "WHERE l.partner_id = %s " \
                        "AND l.account_id IN %s AND " + self.query +" " \
                        "AND m.state IN %s " \
                        " " + RECONCILE_TAG + " "\
                        "ORDER BY l.date",
                        (self.partner[0], tuple(self.account_ids), tuple(move_state)))
                res = self.cr.dictfetchall()
            else:
                self.cr.execute(
                    "SELECT l.id, l.date, j.code, acc.code as a_code, acc.name as a_name, l.ref, m.name as move_name, l.name, l.debit, l.credit, l.amount_currency,l.currency_id, c.symbol AS currency_code " \
                    "FROM account_move_line l " \
                    "LEFT JOIN account_journal j " \
                        "ON (l.journal_id = j.id) " \
                    "LEFT JOIN account_account acc " \
                        "ON (l.account_id = acc.id) " \
                    "LEFT JOIN res_currency c ON (l.currency_id=c.id)" \
                    "LEFT JOIN account_move m ON (m.id=l.move_id)" \
                    "WHERE l.partner_id = %s " \
                        "AND l.account_id IN %s AND " + self.query +" " \
                        "AND m.state IN %s " \
                        " " + RECONCILE_TAG + " "\
                        "ORDER BY l.date",
                        (partner.id, tuple(self.account_ids), tuple(move_state)))
                res = self.cr.dictfetchall()
            res1=[]
            if data['form']['sch_yr'] == False:
                res1=res
            rid=[]
            if ana:
                if data['form']['sch_yr']:
                    for r in res:
                        rid.append(r['id'])
                    if self.partner:
                        module_fields_ids = self.pool.get('account.move.line').search(self.cr, self.uid, [('partner_id', '=', self.partner[0]), ('analytic_account_id', '=', ana.id)])
                    else:
                        module_fields_ids = self.pool.get('account.move.line').search(self.cr, self.uid, [('partner_id', '=', partner.id), ('analytic_account_id', '=', ana.id)])
                    
                    for r1 in res:
                        for mv_id in module_fields_ids:    
                            if mv_id == r['id']:
                                res1.append(r)
            sum = 0.0
            if self.initial_balance:
                sum = self.init_bal_sum
            for r in res1:
                sum += r['debit'] - r['credit']
                r['progress'] = sum
                full_account.append(r)
            return full_account
        
    def get_start_period(self, data):
        if data.get('form', False) and data['form'].get('period_from', False):
            return self.pool.get('account.period').browse(self.cr,self.uid,data['form']['period_from']).name
        return ''

    def get_end_period(self, data):
        if data.get('form', False) and data['form'].get('period_to', False):
            return self.pool.get('account.period').browse(self.cr, self.uid, data['form']['period_to']).name
        return ''
    
    def _get_start_date(self, data):
        if data.get('form', False) and data['form'].get('date_from', False):
            return data['form']['date_from']
        return ''

    def _get_target_move(self, data):
        if data.get('form', False) and data['form'].get('target_move', False):
            if data['form']['target_move'] == 'all':
                return _('All Entries')
            return _('All Posted Entries')
        return ''

    def _get_end_date(self, data):
        if data.get('form', False) and data['form'].get('date_to', False):
            return data['form']['date_to']
        return ''

    def _get_fiscalyear(self, data):
        if data.get('form', False) and data['form'].get('fiscalyear_id', False):
            return self.pool.get('account.fiscalyear').browse(self.cr, self.uid, data['form']['fiscalyear_id']).name
        return ''
        
        
    
    
class report_partnerledger(osv.AbstractModel):
    _name = 'report.account.report_partnerledger'
    _inherit = 'report.abstract_report'
    _template = 'account.report_partnerledger'
    _wrapped_report_class = partner_ledger_rep
    
    
class report_partnerledger_scheme_yr(osv.AbstractModel):
    _name = 'report.hwseta_finance.report_partnerledger_latest'
    _inherit = 'report.abstract_report'
    _template = 'hwseta_finance.report_partnerledger_latest'
    _wrapped_report_class = partner_ledger_rep    
