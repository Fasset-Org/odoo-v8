# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time
import datetime
from openerp import netsvc
from datetime import timedelta
from openerp import api

from openerp.osv import fields, osv

from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

from dateutil.relativedelta import relativedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
# import stock_indent

class stock_location(osv.Model):
    _inherit = 'stock.location'
    _columns = {
        'manager_id': fields.many2one('res.users', 'Manager'),
        'can_request': fields.boolean('Can request for item ?'),
        'depart_id':fields.many2one('hr.department', 'Department')
    }
stock_location()

class indent_equipment(osv.Model):
    _name = 'indent.equipment'
    _description = 'Equipment'
    
    _columns = {
        'name': fields.char('Name', size=256),
        'code': fields.char('Code', size=16),
    }
    
    _sql_constraints = [
        ('equipment_code', 'unique(code)', 'Equipment code must be unique !'),
    ]
indent_equipment()

class indent_equipment_section(osv.Model):
    _name = 'indent.equipment.section'
    _description = 'Equipment Section'
    
    _columns = {
        'equipment_id': fields.many2one('indent.equipment', 'Equipment', required=True),
        'name': fields.char('Name', size=256),
        'code': fields.char('Code', size=16),
    }
    
    _sql_constraints = [
        ('equipment_section_code', 'unique(equipment_id, code)', 'Section code must be unique per Equipment !'),
    ]
indent_equipment_section()

class account_analytic_account(osv.Model):
    _inherit = 'account.analytic.account'
    _columns = {
        'indent_close': fields.boolean('Close Indents'),
        'purchase_close': fields.boolean('Close Purchase'),
    }
    
    _defaults = {
        'indent_close': False,
        'purchase_close': False
    }
    
account_analytic_account()

class indent_indent(osv.Model):
    _name = 'indent.indent'
    _description = 'Indent'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _order = "approve_date desc"
    
    _track = {
        'state': {
            'indent.mt_indent_waiting_approval': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'waiting_approval',
            'indent.mt_indent_inprogress': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'inprogress',
            'indent.mt_indent_received': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'received',
            'indent.mt_indent_rejected': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'reject'
        },
    }
    
    def _total_amount(self, cr, uid, ids, name, args, context=None):
        result = {}
        for indent in self.browse(cr, uid, ids, context=context):
            total = 0.0
            for line in indent.product_lines:
                total += line.price_subtotal
            result[indent.id] = total
        return result

    def _get_product_line(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('indent.product.lines').browse(cr, uid, ids, context=context):
            result[line.indent_id.id] = True
        return result.keys()

    _columns = {
        'name': fields.char('Indent #', size=256, readonly=True, track_visibility='always'),
        'approve_date': fields.datetime('Approve Date', readonly=True, track_visibility='onchange'),
        'indent_date': fields.datetime('Indent Date', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'required_date': fields.datetime('Required Date', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'indentor_id': fields.many2one('res.users', 'Indentor', required=True, readonly=True, track_visibility='always', states={'draft': [('readonly', False)]}),
        'manager_id': fields.related('department_id', 'manager_id', readonly=True, type='many2one', relation='res.users', string='Department Manager', store=True, states={'draft': [('readonly', False)]}),
        'department_id': fields.many2one('stock.location', 'Locations', required=True, readonly=True, track_visibility='onchange', states={'draft': [('readonly', False)]}, domain=[('can_request','=', True)]),
        'dept_id': fields.related('department_id', 'depart_id', readonly=True, type='many2one', relation = 'hr.department', string='Department', store=True, states={'draft': [('readonly', False)]}, ),
        'analytic_account_id': fields.many2one('account.analytic.account', 'Project', ondelete="cascade",readonly=True, track_visibility='onchange', states={'draft': [('readonly', False)]}),
        'requirement': fields.selection([('ordinary', 'Ordinary'), ('urgent', 'Urgent')], 'Requirement', readonly=True, required=True, track_visibility='onchange', states={'draft': [('readonly', False)]}),
        'type': fields.selection([('new', 'Purchase Indent'), ('existing', 'Repairing Indent')], 'Type', required=True, track_visibility='onchange', readonly=True, states={'draft': [('readonly', False)]}),
        'product_lines': fields.one2many('indent.product.lines', 'indent_id', 'Products', readonly=True, states={'draft': [('readonly', False)], 'waiting_approval': [('readonly', False)]}),
        'picking_id': fields.many2one('stock.picking','Picking'),
        'in_picking_id': fields.many2one('stock.picking','Picking'),
        'description': fields.text('Additional Information', readonly=True, states={'draft': [('readonly', False)]}),
        'company_id': fields.many2one('res.company', 'Company', readonly=True, states={'draft': [('readonly', False)]}),
        'active': fields.boolean('Active'),
        'item_for': fields.selection([('store', 'Store'), ('capital', 'Capital')], 'Purchase for', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'amount_total': fields.function(_total_amount, type="float", string='Total',
            store={
                'indent.indent': (lambda self, cr, uid, ids, c={}: ids, ['product_lines'], 20),
                'indent.product.lines': (_get_product_line, ['price_subtotal', 'product_uom_qty', 'indent_id'], 20),
            }),
        'state':fields.selection([('draft', 'Draft'), ('confirm', 'Confirm'), ('waiting_approval', 'Waiting for Approval'), ('inprogress', 'In Progress'), ('received', 'Received'), ('reject', 'Rejected')], 'State', readonly=True, track_visibility='onchange'),
        'approver_id': fields.many2one('res.users', 'Authority', readonly=True, track_visibility='always', states={'draft': [('readonly', False)]}, help="who have approve or reject indent."),
        'product_id': fields.related('product_lines', 'product_id', string='Products', type='many2one', relation='product.product'),
        
        'equipment_id': fields.many2one('indent.equipment', 'Equipment',  readonly=True, states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]}),
        'equipment_section_id': fields.many2one('indent.equipment.section', 'Section', readonly=True, states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]}),
        
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse', help="default warehose where inward will be taken", readonly=True, states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]}),
        'move_type': fields.selection([('direct', 'Partial'), ('one', 'All at once')], 'Receive Method', track_visibility='onchange', readonly=True, required=True, states={'draft':[('readonly', False)], 'cancel':[('readonly',True)]}, help="It specifies goods to be deliver partially or all at once"),
    }

    def _default_stock_location(self, cr, uid, context=None):
        #TODO: need to improve this try except with some better option
        try:
            stock_location = self.pool.get('ir.model.data').get_object(cr, uid, 'stock_indent', 'location_production1').id
        except:
            stock_location = False
        return stock_location

    def _get_required_date(self, cr, uid, context=None):
        return datetime.datetime.strftime(datetime.datetime.today() + timedelta(days=7), DEFAULT_SERVER_DATETIME_FORMAT)
    
    def _get_date_planned(self, cr, uid, indent, line, start_date, context=None):
        date_planned = datetime.datetime.strptime(start_date, DEFAULT_SERVER_DATETIME_FORMAT) + relativedelta(days=line.delay or 0.0)
        return date_planned

    def _get_default_warehouse(self, cr, uid, context=None):
        warehouse_obj = self.pool.get('stock.warehouse')
        company_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.id
        warehouse_ids = warehouse_obj.search(cr, uid, [('company_id', '=', company_id)], context=context)
        warehouse_id = warehouse_ids and warehouse_ids[0] or False
        return warehouse_id
    
    _defaults = {
        'state': 'draft',
        'indent_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'required_date': _get_required_date,
        'indentor_id': lambda self, cr, uid, context: uid,
        'requirement': 'ordinary',
        'type': 'new',
        'department_id':_default_stock_location,
        'item_for':'store',
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'indent.indent', context=c),
        'name':"/",
        'active': True,
        'approver_id':False,
        'move_type':'one',
        'warehouse_id':_get_default_warehouse
    }
    
    def _check_purchase_limit(self, cr, uid, ids, context=None):
        return True
    
    _constraints = [
        (_check_purchase_limit, 'You have exided your purchase limit for the current period !.', ['amount_total']),
    ]
    
    def onchange_requirement(self, cr, uid, ids, indent_date, requirement='urgent', context=None):
        vals = {}
        days_delay = 7
        if requirement == 'urgent':
            days_delay = 3
        #TODO: for the moment it will count the next days based on the system time 
        #and not based on the indent_date available on the indent. 
        required_day = datetime.datetime.strftime(datetime.datetime.today() + timedelta(days=days_delay), DEFAULT_SERVER_DATETIME_FORMAT)
        vals.update({'value':{'required_date':required_day}})
        return vals
    
    def _needaction_domain_get(self, cr, uid, context=None):
        return [('state', '=', 'waiting_approval')]

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        required_date = datetime.datetime.strftime(datetime.datetime.today() + timedelta(days=7), DEFAULT_SERVER_DATETIME_FORMAT)
        default.update({
            'name': "/",
            'indent_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'requirement': 'ordinary',
            'picking_id': False,
            'indent_authority_ids': [],
            'state': 'draft',
            'approver_id':False,
            'approve_date':False,
            'required_date':required_date
        })
        return super(indent_indent, self).copy(cr, uid, id, default, context=context)

    def onchange_item(self, cr, uid, ids, item_for=False, context=None):
        result = {}
        if not item_for or item_for == 'store':
            result['analytic_account_id'] = False
        return {'value': result}
    
    def indent_confirm(self, cr, uid, ids, context=None):
        for indent in self.browse(cr, uid, ids, context=context): 
            if not indent.product_lines:
                raise osv.except_osv(_('Warning!'),_('You cannot confirm an indent %s which has no line.' % (indent.name)))
            res = {
               'name':self.pool.get('ir.sequence').get(cr, uid, 'stock.indent'),
               'state': 'waiting_approval'
            }
            self.write(cr, uid, [indent.id], res, context=context)

            # Add all authorities of the indent as followers
            followers = []
            if indent.indentor_id and indent.indentor_id.partner_id and indent.indentor_id.partner_id.id:
                followers.append(indent.indentor_id.partner_id.id)
            if indent.manager_id and indent.manager_id.partner_id and indent.manager_id.partner_id.id:
                followers.append(indent.manager_id.partner_id.id)

            for follower in followers:
                self.write(cr, uid, [indent.id], {'message_follower_ids': [(4, follower)]}, context=context)

        return True

    def _prepare_indent_line_procurement(self, cr, uid, indent, line, move_id, date_planned, context=None):
        location_id = indent.warehouse_id.lot_stock_id.id

        res = {
            'name': line.name,
            'origin': indent.name,
            'indent_id': indent.id,
            'analytic_account_id': indent.analytic_account_id.id,
            'date_planned': date_planned,
            'product_id': line.product_id.id,
            'product_qty': line.product_uom_qty,
            'product_uom': line.product_uom.id,
            'product_uos_qty': (line.product_uos and line.product_uos_qty)\
                    or line.product_uom_qty,
            'product_uos': (line.product_uos and line.product_uos.id)\
                    or line.product_uom.id,
            'location_id': location_id,
            'procure_method': line.type,
            'move_id': move_id,
            'note': line.name,
            'price': line.price_unit or 0.0,
        }
        if indent.company_id:
            res = dict(res, company_id = indent.company_id.id)
        return res

    def _prepare_indent_line_move(self, cr, uid, indent, line, picking_id, date_planned, context=None):
        
        location_id = indent.warehouse_id.lot_stock_id.id

        res = {
            'name': line.name,
            'indent_id':indent.id,
            'picking_id': picking_id,
            'product_id': line.product_id.id,
            'date': date_planned,
            'product_uom_qty':line.product_uom_qty,
            'date_expected': date_planned,
            'product_uom': line.product_uom.id,
            'product_uos_qty': (line.product_uos and line.product_uos_qty) or line.product_uom_qty,
            'product_uos': (line.product_uos and line.product_uos.id)\
                    or line.product_uom.id,
            'location_id': location_id,
            'location_dest_id': indent.department_id.id,
            'state': 'draft',
            'price_unit': line.product_id.standard_price or 0.0
        }

        if line.product_id.type in ('service'):
            if not line.original_product_id:
                raise osv.except_osv(_("Warning !"), _("You must define material or parts that you are going to repair !"))

            upd_res = {
                'product_id':line.original_product_id.id,
                'product_uom': line.original_product_id.uom_id.id,
                'product_uos':line.original_product_id.uom_id.id
            }
            res.update(upd_res)

        if indent.company_id:
            res = dict(res, company_id = indent.company_id.id)
        return res

    def _prepare_indent_picking(self, cr, uid, indent, context=None):
        pick_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking')
        res = {
            'name': pick_name,
            'origin': indent.name,
            'date': indent.indent_date,
            'type': 'internal',
            'move_type':indent.move_type,
            'picking_type_id':1,
        }
        if indent.company_id:
            res = dict(res, company_id = indent.company_id.id)
        return res

    def _create_pickings_and_procurements(self, cr, uid, indent, product_lines, picking_id=False, context=None):
        move_obj = self.pool.get('stock.move')
        picking_obj = self.pool.get('stock.picking')
        procurement_obj = self.pool.get('procurement.order')
        proc_ids = []
        todo_moves = []

        for line in product_lines:
            date_planned = self._get_date_planned(cr, uid, indent, line, indent.indent_date, context=context)

            if line.product_id:
                move_id = False
                if not picking_id:
                    picking_id = picking_obj.create(cr, uid, self._prepare_indent_picking(cr, uid, indent, context=context))
                
                move_id = move_obj.create(cr, uid, self._prepare_indent_line_move(cr, uid, indent, line, picking_id, date_planned, context=context), context=context)
                todo_moves.append(move_id)

                proc_id = procurement_obj.create(cr, uid, self._prepare_indent_line_procurement(cr, uid, indent, line, move_id, date_planned, context=context))
                proc_ids.append(proc_id)
        if picking_id:
            ## changes it is need to call method in odoo8 becoz. does nt have workflow
            chece_ids = picking_obj.action_confirm(cr, uid, picking_id, context)
#             wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
        for proc_id in proc_ids:
            ## changes  it is need to call method in odoo8 becoz does nt have workflow
            run_pro = procurement_obj.run(cr, uid, proc_id, '', context)
#             wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)

        return picking_id
    
    def _check_gatepass_flow(self, cr, uid, indent, context):
        if indent.type == 'existing':
            return True
        else:
            return False
        
    def create_transfer_move(self, cr, uid, indent, internal=None, context=None):
        move_obj = self.pool.get('stock.move')
        picking_obj = self.pool.get('stock.picking')
        product_pool = self.pool.get('product.product')
        location_id = indent.warehouse_id.lot_stock_id.id
        
        todo_moves = []
        
        picking_id = False
        for line in indent.product_lines:
            date_planned = self._get_date_planned(cr, uid, indent, line, indent.indent_date, context=context)

            if line.product_id:
                move_id = False
#                 if not picking_id:
#                     picking_id = picking_obj.create(cr, uid, self._prepare_indent_picking(cr, uid, indent, context=context))
                
                res = self._prepare_indent_line_move(cr, uid, indent, line, picking_id, date_planned, context=context)
                res.update({
                    'location_id': indent.department_id.id,
                    'location_dest_id': location_id
                })
                if internal:
                    move_id = move_obj.create(cr, uid, res, context=context)
                elif not internal and not product_pool.browse(cr, uid, res.get('product_id')).repair_ok:
                    move_id = move_obj.create(cr, uid, res, context=context)
                if move_id:
                    todo_moves.append(move_id)

#         wf_service = netsvc.LocalService("workflow")
#         if picking_id:
#             wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)

        if todo_moves:
            todo_moves = move_obj.action_confirm(cr, uid, todo_moves)
            move_obj.force_assign(cr, uid, todo_moves)

            picking_id = False

            for move in move_obj.browse(cr, uid, todo_moves):
                picking_id = move.picking_id.id

            self.write(cr, uid, [indent.id], {'in_picking_id': picking_id})
        
#         self.write(cr, uid, [indent.id], {'in_picking_id': picking_id})
        return True
   
    def create_repairing_gatepass(self, cr, uid, indent, context):
        pass
    
    def action_picking_create(self, cr, uid, ids, context=None):
        proc_obj = self.pool.get('procurement.order')
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")
        assert len(ids) == 1, 'This option should only be used for a single id at a time.'
        picking_id = False
        proc_ids = []

        indent = self.browse(cr, uid, ids[0], context=context)
        
        #Check if gatepass is not installed, transfer product to stock for repairing, else 
        #Create a returnable gatepass to send supplier to repair their location\
        gatepass_flow = self._check_gatepass_flow(cr, uid, indent, context)
        if gatepass_flow and indent.type == 'existing':
            self.create_transfer_move(cr, uid, indent, True, context)
        elif not gatepass_flow and indent.type == 'existing':
            self.create_repairing_gatepass(cr, uid, ids, context)
            self.create_transfer_move(cr, uid, indent, False, context)
        
        if indent.product_lines and indent.type == 'new':
            picking_id = self._create_pickings_and_procurements(cr, uid, indent, indent.product_lines, None, context=context)
#         else:
#             picking_id = self._create_pickings_and_procurements(cr, uid, indent, indent.product_lines, None, context=context)
            

        move_ids = move_obj.search(cr,uid,[('picking_id','=',picking_id)])
         
#         pro_ids = proc_obj.search(cr,uid,[('move_id','in',move_ids)])
# #         for line in indent.product_lines:
# #             date_planned = self._get_date_planned(cr, uid, indent, line, indent.indent_date, context=context)
# #             proc_id = proc_obj.create(cr, uid, self._prepare_indent_line_procurement(cr, uid, indent, line, move_ids, date_planned, context=context))
# #             proc_ids.append(proc_id)
#         for pro in pro_ids:
#             proc_obj.run(cr, uid, pro ,'', context)

        ''' old code'''
#         move_ids = move_obj.search(cr,uid,[('picking_id','=',picking_id)])
#         pro_ids = proc_obj.search(cr,uid,[('move_id','in',move_ids)])
#         for pro in pro_ids:
#             wf_service.trg_validate(uid, 'procurement.order', pro, 'button_check', cr)
# 
#         self.write(cr, uid, ids, {'picking_id': picking_id, 'state' : 'inprogress', 'message_follower_ids': [(4, indent.approver_id and indent.approver_id.partner_id and indent.approver_id.partner_id.id)]}, context=context)
#         return picking_id

        self.write(cr, uid, ids, {'picking_id': picking_id, 'state' : 'inprogress', 'message_follower_ids': [(4, indent.approver_id and indent.approver_id.partner_id and indent.approver_id.partner_id.id)]}, context=context)
    def check_reject(self, cr, uid, ids):
        res = {
           'approver_id':uid
        }
        self.write(cr, uid, ids, res)
        return True

    def check_approval(self, cr, uid, ids, context=None):
        res = {
           'approver_id':uid,
           'approve_date':time.strftime('%Y-%m-%d %H:%M:%S')
        }
        self.write(cr, uid, ids, res)
        return True

    def action_receive_products(self, cr, uid, ids, context=None):
        '''
        This function returns an action that display internal move of given indent ids.
        '''
        assert len(ids) == 1, 'This option should only be used for a single id at a time'
        picking_id = self.browse(cr, uid, ids[0], context=context).picking_id.id
        res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_form')
        result = {
            'name': _('Receive Product'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': res and res[1] or False,
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': picking_id,
        }
        return result

    #TODO: improve this method, gatepass object not allowed to access in this module   
    def action_deliver_products(self, cr, uid, ids, context=None):
        '''
        This function returns an action that display internal move of given indent ids.
        '''
        gatepass_pool = self.pool.get('stock.gatepass')
        
        assert len(ids) == 1, 'This option should only be used for a single id at a time'
        picking_id = self.browse(cr, uid, ids[0], context=context).in_picking_id.id
        if not picking_id:
            gatepass_ids = gatepass_pool.search(cr, uid, [('indent_id','=',ids[0])])
            if gatepass_ids:
                picking_id = gatepass_pool.browse(cr, uid, gatepass_ids[0]).out_picking_id.id
        
        if not picking_id:
            raise osv.except_osv(_('Invalid Action!'), _('You have not created gatepass / delivery order for Repairing Indent !'))
        
        res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_form')
            
        result = {
            'name': _('Receive Product'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': res and res[1] or False,
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': picking_id,
        }
        return result

    def unlink(self, cr, uid, ids, context=None):
        for indent in self.browse(cr, uid, ids):
            if indent.state != 'draft':
                raise osv.except_osv(_('Invalid Action!'), _('You cannot delete this indent'))
        return super(indent_indent, self).unlink(cr, uid, ids, context=context)

indent_indent()

class indent_product_lines(osv.Model):
    _name = 'indent.product.lines'
    _description = 'Indent Product Lines'

    def _amount_subtotal(self, cr, uid, ids, name, args, context=None):
        result = {}
        for line in self.browse(cr, uid, ids, context=context):
            result[line.id] = (line.product_uom_qty * line.price_unit)
        return result

    _columns = {
        'indent_id': fields.many2one('indent.indent', 'Indent', required=True, ondelete='cascade'),
        'name': fields.text('Description', required=True),
#         'product_id': fields.many2one('product.product', 'Product', required=True, domain=[('supply_method','=','buy')]),
        'product_id': fields.many2one('product.product', 'Product', required=True,),
        'original_product_id': fields.many2one('product.product', 'Product to be Repaired'),
        'type': fields.selection([('make_to_stock', 'Stock'), ('make_to_order', 'Purchase')], 'Procure', required=True,
         help="From stock: When needed, the product is taken from the stock or we wait for replenishment.\nOn order: When needed, the product is purchased or produced."),
        'product_uom_qty': fields.float('Quantity Required', digits_compute= dp.get_precision('Product UoS'), required=True),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure', required=True),
        'product_uos_qty': fields.float('Quantity (UoS)' ,digits_compute= dp.get_precision('Product UoS')),
        'product_uos': fields.many2one('product.uom', 'Product UoS'),
        'price_unit': fields.float('Price', required=True, digits_compute= dp.get_precision('Product Price'), help="Price computed based on the last purchase order approved."),
        'price_subtotal': fields.function(_amount_subtotal, string='Subtotal', digits_compute= dp.get_precision('Account'), store=True),
        'qty_available': fields.float('In Stock'),
        'virtual_available': fields.float('Forecasted Qty'),
        'delay': fields.float('Lead Time', required=True),
        'name': fields.text('Purpose', required=True),
        'specification': fields.text('Specification'),
        'sequence':fields.integer('Sequence'),
        
        'indent_type': fields.selection([('new', 'Purchase Indent'), ('existing', 'Repairing Indent')], 'Type')
    }

    def _get_uom_id(self, cr, uid, *args):
        result = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product', 'product_uom_unit')
        return result and result[1] or False
    
    def _get_default_type(self, cr, uid, *args):
        context = args[0]
        return context.get('indent_type')
    
    _defaults = {
        'product_uom_qty': 1,
        'product_uos_qty': 1,
        'type': 'make_to_order',
        'delay': 0.0,
        'indent_type':_get_default_type
    }
    
    def _check_stock_available(self, cr, uid, ids, context=None):
        for move in self.browse(cr, uid, ids, context):
            if move.type == 'make_to_stock' and move.product_uom_qty > move.qty_available:
                return False
        return True
    
    _constraints = [
        (_check_stock_available, 'You can not procure more quantity form stock then the available !.', ['Quantity Required']),
    ]
    
    def onchange_product_id(self, cr, uid, ids, product_id=False, product_uom_qty=0.0, product_uom=False, price_unit=0.0, qty_available=0.0, virtual_available=0.0, name='', analytic_account_id=False, indent_type=False, context=None):
        result = {}
        product_obj = self.pool.get('product.product')
        if not product_id:
            return {'value': {'product_uom_qty': 1.0, 'product_uom': False, 'price_unit': 0.0, 'qty_available': 0.0, 'virtual_available': 0.0, 'name': '', 'delay': 0.0}}

        product = product_obj.browse(cr, uid, product_id, context=context)
        
        if not product.seller_ids:
            raise osv.except_osv(_("Warning !"), _("You must define at least one supplier for this product"))
        
        if product.qty_available > 0:
            result['type'] = 'make_to_stock'
        else:
            result['type'] = 'make_to_order'
        
        #result['name'] = product_obj.name_get(cr, uid, [product.id])[0][1]
        result['product_uom'] = product.uom_id.id
        result['price_unit'] = product.standard_price
        result['qty_available'] = product.qty_available
        result['virtual_available'] = product.virtual_available
        result['delay'] = product.seller_ids[0].delay
        result['specification'] = product_obj.name_get(cr, uid, [product.id])[0][1]
        
        if product.type == 'service':
            result['original_product_id'] = product.repair_id.id
            result['type'] = 'make_to_order'
        else:
            result['original_product_id'] = False
        return {'value': result}
    
indent_product_lines()

class procurement_order(osv.osv):
    _inherit = 'procurement.order'
    _columns = {
        'indent_id': fields.many2one('indent.indent', 'Indent'),
        'analytic_account_id': fields.many2one('account.analytic.account', 'Project'),
        'price': fields.float('Price'),
        'move_id':fields.many2one('stock.move', 'Reservation'),
    }

    def _prepare_line_purchase(self, cr, uid, name, procurement, qty, uom_id, price, schedule_date, taxes):
        line_vals = {
            'name': name,
            'indent_id': procurement.indent_id and procurement.indent_id.id or False,
            'account_analytic_id': procurement.analytic_account_id and procurement.analytic_account_id.id or False,
            'product_qty': qty,
            'product_id': procurement.product_id.id,
            'product_uom': uom_id,
            'price_unit': price or 0.0,
            'date_planned': schedule_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'move_dest_id': False,
            'taxes_id': [(6, 0, taxes)],
        }
        return line_vals

    def make_po(self, cr, uid, ids, context=None):
        """ Make purchase order from procurement
        @return: New created Purchase Orders procurement wise
        """
        res = {}
        if context is None:
            context = {}
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        uom_obj = self.pool.get('product.uom')
        prod_obj = self.pool.get('product.product')
        acc_pos_obj = self.pool.get('account.fiscal.position')
        seq_obj = self.pool.get('ir.sequence')
        warehouse_obj = self.pool.get('stock.warehouse')
        requisition_obj = self.pool.get('purchase.requisition')
        for procurement in self.browse(cr, uid, ids, context=context):
            partner = procurement.product_id.seller_id  # Taken Main Supplier of Product of Procurement.
            seller_qty = procurement.product_id.seller_qty
            partner_id = partner.id
            pricelist_id = partner.property_product_pricelist_purchase.id
            warehouse_id = warehouse_obj.search(cr, uid, [('company_id', '=', procurement.company_id.id or company.id)], context=context)
            uom_id = procurement.product_id.uom_po_id.id

            qty = uom_obj._compute_qty(cr, uid, procurement.product_uom.id, procurement.product_qty, uom_id)
            if seller_qty:
                qty = max(qty, seller_qty)

            schedule_date = self._get_purchase_schedule_date(cr, uid, procurement, company, context=context)
            purchase_date = self._get_purchase_order_date(cr, uid, procurement, company, schedule_date, context=context)

            # Passing partner_id to context for purchase order line integrity of Line name
            new_context = context.copy()
            new_context.update({'lang': partner.lang, 'partner_id': partner_id})

            product = prod_obj.browse(cr, uid, procurement.product_id.id, context=new_context)
            taxes_ids = procurement.product_id.supplier_taxes_id
            taxes = acc_pos_obj.map_tax(cr, uid, partner.property_account_position, taxes_ids)

            name = ''
            if product.description_purchase:
                name = product.description_purchase
            line_vals = self._prepare_line_purchase(cr, uid, name, procurement, qty, uom_id, procurement.price, schedule_date, taxes)
            name = seq_obj.get(cr, uid, 'purchase.order') or _('PO: %s') % procurement.name
            
            if not warehouse_id:
                raise osv.except_osv(_("Warning !"), _("You must define at least one warehouse for current company !"))
            ## change location id as per odoo 7 to 8 requirement
            po_vals = {
                'name': name,
                'origin': procurement.origin,
                'partner_id': partner_id,
#                 'location_id': warehouse_obj.browse(cr, uid, warehouse_id[0]).lot_input_id.id,
                'location_id':procurement.location_id.id,
                'warehouse_id': warehouse_id and warehouse_id[0] or False,
                'pricelist_id': pricelist_id,
                'date_order': purchase_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'company_id': procurement.company_id.id,
                'fiscal_position': partner.property_account_position and partner.property_account_position.id or False,
                'payment_term_id': partner.property_supplier_payment_term.id or False,
            }
            res[procurement.id] = self.create_procurement_purchase_order(cr, uid, procurement, po_vals, line_vals, context=new_context)

            requisition_id = False
            if 'purchase_requisition' in prod_obj._columns and procurement.product_id.purchase_requisition:
                requisition_id = requisition_obj.create(cr, uid,
                    {
                    
                        'origin': procurement.origin,
                        'date_end': procurement.date_planned,
                        'warehouse_id':warehouse_id and warehouse_id[0] or False,
                        'company_id':procurement.company_id.id,
                        'line_ids': [(0, 0, {
                            'product_id': procurement.product_id.id,
                            'product_uom_id': procurement.product_uom.id,
                            'product_qty': procurement.product_qty
                        })],
                    })
                requisition_obj.write(cr, uid, [requisition_id], {'purchase_ids': [(6, 0, res.values())]}, context=context)
            self.write(cr, uid, [procurement.id], {'state': 'running', 'purchase_id': res[procurement.id], 'requisition_id': requisition_id})
        self.message_post(cr, uid, ids, body=_("Draft Purchase Order created"), context=context)
        return res

procurement_order()

class product_product(osv.Model):
    _inherit = 'product.product'
 
    _columns = {
        'repair_id': fields.many2one('product.product', 'Repairable Product', domain=[('type','!=','service')]),
        'repair_ok': fields.boolean('Can Move for Repairing'),
    }
    
    _defaults = {
        'repair_ok':True
    }
product_product()

class stock_picking(osv.Model):
    _inherit = 'stock.picking'

    def action_confirm(self, cr, uid, ids, context=None):
        #Implement method that will check further verification for authority
        return super(stock_picking, self).action_confirm(cr, uid, ids, context=context)
 
    def check_approval(self, cr, uid, ids):
        #Implement method that will check further verification for authority
        return True

    def draft_force_assign(self, cr, uid, ids, *args):
        res = super(stock_picking, self).draft_force_assign(cr, uid, ids, *args)
        for picking in self.browse(cr, uid, ids):
            followers = []
            for move in picking.move_lines:
                if move.indent_id and move.indent_id.indentor_id and move.indent_id.indentor_id.partner_id and move.indent_id.indentor_id.partner_id.id:
                    followers.append(move.indent_id.indentor_id.partner_id.id)
            for follower in followers:
                self.write(cr, uid, [picking.id], {'message_follower_ids': [(4, follower)]})
        return res
    
    ## this method need to overwrite for indent state in received (migration changes) 
    @api.cr_uid_ids_context
    def do_transfer(self, cr, uid, picking_ids, context=None):
        if context is None:
            context = {}
        res = super(stock_picking, self).do_transfer(cr, uid, picking_ids, context=context)
        move_obj = self.pool.get('stock.move')
        move_id = move_obj.search(cr, uid, [('picking_id','in',picking_ids)])
        for move_record in move_obj.browse(cr, uid, move_id):
            ids = move_record.indent_id.id
            self.pool.get('indent.indent').write(cr, uid, ids, {'picking_id': picking_ids[0], 'state' : 'received',}, context=context)
        return res
stock_picking()

class purchase_order_line(osv.Model):
    _inherit = 'purchase.order.line'

    _columns = {
        'indent_id': fields.many2one('indent.indent', 'Indent'),
    }
    
    
    def create(self, cr, uid, vals, context=None):
        if 'name' in vals:
            if vals['name'] == '' or vals['name'] == None or vals['name'] == False:
                product = self.pool.get('product.product').browse(cr, uid, vals['product_id'])
                vals['name'] = product.name
            
        return super(purchase_order_line, self).create(cr, uid, vals, context)
    
    
    
purchase_order_line()

class purchase_order(osv.Model):
    _inherit = 'purchase.order'
    
    def create(self, cr, uid, vals, context=None):
        indent_obj = self.pool.get('indent.indent')
        if 'partner_id' in vals and vals['partner_id'] == False:
            
            raise osv.except_osv(_("Warning !"), _("You must define at least one supplier !"))
#             if vals['name'] == '' or vals['name'] == None or vals['name'] == False:
#                 product = self.pool.get('product.product').browse(cr, uid, vals['product_id'])
#                 vals['name'] = product.name
        if 'purchase_project_id' not in vals:
            for line in vals['order_line']:
                if line[2] and line[2].get('indent_id',False):
                    indent_id = line[2]['indent_id']
                    indent_record = indent_obj.browse(cr, uid, indent_id)
                    vals['purchase_project_id'] = indent_record.project_id.id
        return super(purchase_order, self).create(cr, uid, vals, context)
    
    

    _columns = {
        'indent_id': fields.related('order_line', 'indent_id', type='many2one', relation='indent.indent', string='Indent')
    }
    
    
    
    
## need to change method code for confirm the purchase order..........
#     def _prepare_order_line_move(self, cr, uid, order, order_line, picking_id, context=None):
#         res = super(purchase_order, self)._prepare_order_line_move(cr, uid, order=order, order_line=order_line, picking_id=picking_id, context=context)
#         res = dict(res, indent_id = order_line.indent_id and order_line.indent_id.id or False)
#         return res
    def _prepare_order_line_move(self, cr, uid, order, order_line, picking_id, group_id, context=None):
        res = super(purchase_order, self)._prepare_order_line_move(cr, uid, order, order_line, picking_id, group_id, context)
#         res = dict(res[0], (0,0,{'indent_id' :order_line.indent_id.id or False}))
        if order_line.indent_id:
            res[0].update({'indent_id':order_line.indent_id.id})
        return res

purchase_order()



class stock_move(osv.Model):
    _inherit = 'stock.move'

    _columns = {
        'indent_id': fields.many2one('indent.indent', 'Indent'),
        'indentor_id':fields.related('indent_id', 'indentor_id', relation='res.users', type='many2one', string='Indentor', store=True, readonly=True),
        'department_id': fields.many2one('stock.location', string='Department'), 
        'indent_date': fields.related('indent_id', 'indent_date', type='datetime', relation='indent.indent', string='Indent Date', readonly=True),
    }

stock_move()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
