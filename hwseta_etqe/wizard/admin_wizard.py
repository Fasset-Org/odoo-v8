# coding=utf-8
from openerp import models, fields, tools, api, _
import datetime
DEBUG = True

if DEBUG:
	import logging

	logger = logging.getLogger(__name__)


	def dbg(msg):
		logger.info(msg)
else:
	def dbg(msg):
		pass

class seta_admin_log(models.Model):
	_name = 'seta.admin.log'

	name = fields.Char()
	text = fields.Text()

class seta_admin_wizard(models.TransientModel):
	_name = 'seta.admin.wizard'

	input_field = fields.Char()
	quals = fields.Many2one('provider.qualification')
	start_date = fields.Date()
	end_date = fields.Date()
	accreditation = fields.Char()
	provider = fields.Char()
	search_by = fields.Selection([
		('database_id', 'Database ID'), ('assessor_ref', 'Assessor Ref'),
		('provider_ref', 'Provider Ref'), ('moderator_ref', 'Moderator Ref'),
	])

	am_reg_no = fields.Char()
	assessor_moderator_ref = fields.Char()

	@api.one
	def reject_accreditation(self):
		prov = False
		txt = 'ticket: %s' % self.input_field
		if self.accreditation:
			accred = self.env['provider.accreditation'].search([('provider_accreditation_ref','=',self.accreditation)]).id
			if accred:
				self._cr.execute(
					"update provider_accreditation set denied = 't',final_state='Rejected' where provider_accreditation_ref='%s'" % (
						self.accreditation))
				# accred.write({'denied':True,'final_state':'Rejected'})
				txt += 'the accreditation with ref: %s has been rejected by %s\n' % (self.accreditation, self.env.user.login)
		if self.search_by and self.provider:
			if self.search_by == 'database_id':
				prov = self.env['res.partner'].search(
					[('id', '=', self.provider)])
			elif self.search_by == 'provider_ref':
				prov = self.env['res.partner'].search(
					[('provider_accreditation_num', '=', self.provider)])
			else: raise Warning("incorrect option selected in search by.")
			prov.user_id.unlink()
			self._cr.execute("delete from etqe_as_provider_rel where provider_id=%s" % prov.id)
			self._cr.execute("delete from etqe_mo_provider_rel where provider_id=%s" % prov.id)
			if prov:
				self._cr.execute("delete from res_partner where id=%s" % prov.id)
				txt += 'the provider with accreditation number/ID: %s was input for deletion' % self.provider
		log = self.env['seta.admin.log'].create({'name': self.input_field, 'text': txt})

	@api.one
	def reject_am_reg(self):
		txt = 'ticket: %s \n' % self.input_field
		if self.am_reg_no:
			reg = self.am_reg_no
			self._cr.execute(
				"update assessors_moderators_register set approved=\'f\',denied=\'t\', state=\'denied\', final_state=\'Rejected\' where assessors_moderators_ref=\'%s\';" % reg)
			txt += 'register with reference: %s was deleted' % reg
		if self.search_by and self.assessor_moderator_ref:
			if self.search_by == 'assessor_ref':

				ref = self.assessor_moderator_ref
				ass = self.env['hr.employee'].search(
					[('assessor_seq_no', '=', ref)])
				if len(ass) > 1:
					raise Warning('please use database ID, there are multiple records found')
				for x in ass.as_provider_rel_id:
					x.unlink()
				self._cr.execute("delete from etqe_assessors_provider_accreditation_rel where assessors_id=\'%s\';" % ass.id)
				self._cr.execute("delete from hr_employee where assessor_seq_no=\'%s\';" % ref)
				txt += 'assessor with reg: %s was deleted' % ref
			elif self.search_by == 'moderator_ref':
				ref = self.assessor_moderator_ref
				mod = self.env['hr.employee'].search(
					[('moderator_seq_no', '=', ref)])
				if len(mod) > 1:
					raise Warning('please use database ID, there are multiple records found')
				for x in mod.mo_provider_rel_id:
					x.unlink()
				self._cr.execute("delete from etqe_moderators_provider_accreditation_rel where moderators_id=\'%s\';" % mod.id)
				self._cr.execute("delete from hr_employee where moderator_seq_no=\'%s\';" % ref)
				txt += 'moderator with reg: %s was deleted' % ref
			elif self.search_by == 'database_id':
				ref = self.assessor_moderator_ref
				self._cr.execute("delete from etqe_moderators_provider_accreditation_rel where moderators_id=\'%s\';" % ref)
				self._cr.execute(
					"delete from etqe_assessors_provider_accreditation_rel where assessors_id=\'%s\';" % ref)
				self._cr.execute("delete from hr_employee where id=\'%s\';" % ref)
				txt += 'assessor/moderator with ID: %s was deleted' % ref
			else:
				raise Warning("incorrect option selected in search by.")
		log = self.env['seta.admin.log'].create({'name': self.input_field, 'text': txt})

	learner_reg_no = fields.Char()

	@api.one
	def delete_learner(self):
		txt = 'ticket: %s \n' % self.input_field
		if self.learner_reg_no:
			learner = self.learner_reg_no
			self._cr.execute(
				"delete from learner_assessment_verify_line where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)
			self._cr.execute(
				"delete from learner_assessment_evaluate_line where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)
			self._cr.execute(
				"delete from learner_assessment_achieve_line where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)
			self._cr.execute(
				"delete from learner_assessment_achieved_line where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)

			self._cr.execute(
				"delete from learner_assessment_line_for_lp where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)
			self._cr.execute(
				"delete from learner_assessment_achieve_line_for_lp where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)
			self._cr.execute(
				"delete from learner_assessment_achieved_line_for_lp where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)
			self._cr.execute(
				"delete from learner_assessment_verify_line_for_lp where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)
			self._cr.execute(
				"delete from learner_assessment_evaluate_line_for_lp where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)
			# sp section
			self._cr.execute(
				"delete from learner_assessment_line where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)
			self._cr.execute(
				"delete from learner_assessment_line_for_skills where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)
			self._cr.execute(
				"delete from learner_assessment_verify_line_for_skills where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)
			self._cr.execute(
				"delete from learner_assessment_evaluate_line_for_skills where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)
			self._cr.execute(
				"delete from learner_assessment_achieve_line_for_skills where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)
			self._cr.execute(
				"delete from learner_assessment_achieved_line_for_skills where learner_id in (select id from hr_employee where learner_reg_no=\'%s\');" % learner)
			self._cr.execute("delete from hr_employee where learner_reg_no=\'%s\';" % learner)
			txt += 'learner with reg: %s was deleted'
			log = self.env['seta.admin.log'].create({'name': self.input_field, 'text': txt})

	@api.one
	def relink_am_user(self):
		usr_list = []
		rm_usr_list = []
		grp = self.env['res.groups'].search([('id','in',[53,54])])
		for g in grp:
			for usr in g.users.ids:
				usr_list.append(usr)
		dbg(usr_list)
		users = self.env['res.users'].search([('id','in',usr_list),('assessor_moderator_id','=',False)])
		for usr in users:
			if not 'fasset.org.za' in usr.login and not usr.login == 'admin':
				dbg(usr)
				emp = self.env['hr.employee'].search([('work_email','=',usr.login)])
				if emp:
					emp = max(emp)
					usr.assessor_moderator_id = emp.id
				else:
					regs = self.env['assessors.moderators.register'].search([('work_email','=',usr.login)])
					if regs:
						new = True
						for reg in regs:
							if reg.already_registered and reg.is_extension_of_scope:
								new = False

						if new:
							dbg('new is tru')
							txt = 'unlinked user:' + str(usr.login) + '\n found registrations:' + str([x.assessors_moderators_ref for x in regs])
							dbg(txt)
							self.env['seta.admin.log'].create({'name': self.input_field, 'text': txt})
							if usr:
								dbg('removing')
								usr.unlink()
					else:
						dbg('NOT removing, no regs ' + str(usr))
					# raise Warning(reg)


		# raise Warning(users)


	@api.one
	def link_user_am(self):
		counter = 0
		am_recs = self.env['hr.employee'].search([('user_id','=',False),'|',('is_assessors','=',True),('is_moderators','=',True)])
		dbg(len(am_recs))
		for am in am_recs:
			counter += 1
			dbg(am)
			dbg(counter)
			mail = am.work_email
			dbg(mail)
			usr = self.env['res.users'].search([('login','=',mail)])
			if usr:
				dbg('set usr')
				am.user_id = usr.id


	@api.one
	def switch_old_am_links(self):
		# usrs = self.env['res.users'].search([('id','=',117448)])
		# for usr in usrs:
		# 	possible_profiles = [x. id for x in self.env['hr.employee'].search([('work_email','=',usr.login)])]
		# 	dbg(possible_profiles)
		# 	if len(possible_profiles) > 1:
		# 		proper = max(possible_profiles)
		# 		dbg(proper)
		# 		usr.assessor_moderator_id = proper
		ass_group = self.env.ref('hwseta_etqe.group_assessors')
		mod_group = self.env.ref('hwseta_etqe.group_moderators')
		for usr in ass_group.users:
			possible_profiles = [x. id for x in self.env['hr.employee'].search([('work_email','=',usr.login)])]
			if len(possible_profiles) > 1:
				proper = max(possible_profiles)
				usr.assessor_moderator_id = proper
		for usr in mod_group.users:
			possible_profiles = [x. id for x in self.env['hr.employee'].search([('work_email','=',usr.login)])]
			if len(possible_profiles) > 1:
				proper = max(possible_profiles)
				usr.assessor_moderator_id = proper

	@api.one
	def reject_transactions(self):
		if self.input_field:
			rejector = self.env['assessors_moderators_register'].sudo().search([('assessor_moderator_ref','=',self.input_field)])
			if rejector:
				profile_remover = self.env['hr_employee'].sudo().search([('id','=',rejector.related_assessor_moderator)])
				if profile_remover:
					profile_remover.unlink()
				final_state = 'Rejected'
				state = 'denied'
				denied = True
				rejector.sudo().write({'state': state, 'final_state': final_state, 'denied': denied})

	@api.one
	def audit_records(self):
		# d = datetime.now().date()
		# Convert date type from datetime.date type into string
		# d1 = datetime.strftime(d, "%Y-%m-%d %H:%M:%S")
		# d2 = datetime.strftime(d, "%Y-%m-%d 24:59:59")
		# lines = crm_obj.search(self.cr, self.uid, [('date_open', '>=', d1), ('date_open', '<=', d2)])
		bad = [
			'db.backup',
			'mail.message',
			'mass.editing.wizard',
			'mass.object','report.hwseta_etqe.report_learning_programme_statement_of_results',
		]
		if self.input_field:
			user = int(self.input_field)
			date = datetime.datetime.strptime('2020-01-11', '%Y-%m-%d').date()
			end = datetime.datetime.today().date()
			date = '2020-01-11 00:00:00'
			end = datetime.datetime.strftime(datetime.datetime.now(),"%Y-%m-%d %H:%M:%S")
			model_list = [x for x in self.env['ir.model'].search([])]
			msg = ''
			dbg(date)
			dbg(end)
			dbg(user)
			msg += 'model,date,record,count\n'
			for model in model_list:
				if model.model not in bad:
					all_fields = self.env[model.model].fields_get().keys()
					if 'write_date' in all_fields:

						# if model not in res:
						records = self.env[model.model].search(
							[('write_uid', '=', user), ('write_date', '>=', date), ('write_date', '<=', end)], order='write_date')
						if len(records) > 0:
							msg += model.name + ',,,' + str(len(records)) + '\n'
							for rec in records:
								dbg(rec.write_date)
								name = ''
								if 'name' in all_fields:
									if rec.name:
										dbg(type(rec.name))
										dbg(model)
										if model.model == 'assessment.status':
											name = str(rec.name.name)
										else:
											name = rec.name
											name.encode("utf-8")
								else:
									name = str(rec.id)
								msg += ',' + rec.write_date + ',' + name + '\n'
			raise Warning(msg)

	@api.one
	def get_hlamalani_report(self):
		dom = []
		if self.start_date:
			# start = datetime.datetime.strftime(self.start_date,'%Y-%m-%d')
			dom.append(('approval_date','>',self.start_date))
		if self.end_date:
			# end = datetime.datetime.strftime(self.end_date,'%Y-%m-%d')
			dom.append(('approval_date', '<', self.end_date))
		if self.quals:
			quals = [x.id for x in self.quals]
			quals = self.env['provider.qualification'].search([('saqa_qual_id', 'in', quals)])
		else:
			quals = self.env['provider.qualification'].search([])
			dom.append(('is_complete', '=', True))
			dom.append(('approval_date', '!=', False))
		dom.append(('learner_qualification_parent_id', 'in', [q.id for q in quals]))
		dbg(dom)
		achieved_lines = self.env['learner.registration.qualification'].search(dom, order='approval_date desc')
		dbg(achieved_lines)
		msg = 'year,person_name,person_last_name,identification_id,qual,provider_id,province\n'
		for ach in achieved_lines:
			# dbg(ach.read())
			# msg += '\n'
			qual = ach.learner_qualification_parent_id.saqa_qual_id
			if not qual:
				qual = 'not found'
			fn = ach.learner_id.person_name or ach.learner_id.name
			if not fn:
				fn = ach.learner_qualification_id.name or 'not found'
			ln = ach.learner_id.person_last_name
			if not ln:
				ln = ach.learner_qualification_id.person_last_name or 'not found'
			ident = ach.learner_id.learner_identification_id
			if not ident:
				ident = ach.learner_qualification_id.identification_id or 'not found'
			province = ach.learner_id.person_home_province_code.name or ach.learner_id.work_province.name
			if not province:
				province = ach.learner_qualification_id.work_province.name or 'not found'
			prov = ach.provider_id.name
			if not prov:
				prov = 'not found'
			msg += ach.approval_date + ',' + fn + ',' + ln + ',' + ident + ',' + qual + ',' + prov + ',' + province + '\n'
		dbg(msg)
		raise Warning(msg)

	@api.one
	def get_active_assessor_report(self):
		assessors = self.env['hr.employee'].search([('is_assessors', '=', True),('is_active_assessor','=',True)])
		dbg(assessors)
		msg = 'assessor_seq_no,person_name,person_last_name,work_email,province\n'
		for ass in assessors:
			# dbg(ach.read())
			# msg += '\n'
			assessor_seq_no = ass.assessor_seq_no
			if not assessor_seq_no:
				assessor_seq_no = 'not found'
			person_name = ass.person_name
			if not person_name:
				person_name = 'not found'
			person_last_name = ass.person_last_name
			if not person_last_name:
				person_last_name = 'not found'
			work_email = ass.work_email
			if not work_email:
				work_email = 'not found'
			work_province = ass.work_province.name
			if not work_province:
				work_province = 'not found'
			msg += assessor_seq_no + ',' + person_name + ',' + person_last_name + ',' + work_email + ',' + work_province +  '\n'
		dbg(msg)
		raise Warning(msg)

	@api.one
	def get_active_moderator_report(self):
		assessors = self.env['hr.employee'].search([('is_moderators', '=', True), ('is_active_moderator', '=', True)])
		dbg(assessors)
		msg = 'moderator_seq_no,person_name,person_last_name,work_email,province\n'
		for ass in assessors:
			# dbg(ach.read())
			# msg += '\n'
			moderator_seq_no = ass.moderator_seq_no
			if not moderator_seq_no:
				moderator_seq_no = 'not found'
			person_name = ass.person_name
			if not person_name:
				person_name = 'not found'
			person_last_name = ass.person_last_name
			if not person_last_name:
				person_last_name = 'not found'
			work_email = ass.work_email
			if not work_email:
				work_email = 'not found'
			work_province = ass.work_province.name
			if not work_province:
				work_province = 'not found'
			msg += moderator_seq_no + ',' + person_name + ',' + person_last_name + ',' + work_email + ',' + work_province + '\n'
		dbg(msg)
		raise Warning(msg)

	@api.one
	def create_historical_wsp_status(self):
		msg = ''
		status_env = self.env['wsp.submission.track']
		parents = [rec.id for rec in self.env['res.partner'].search([('child_employer_ids','!=',False)])]
		wsp_submission_data = status_env.search(
			[('employer_id', 'in', parents)])
		# dbg(wsp_submission_data)
		for wsp_sub in wsp_submission_data:
			# dbg(wsp_sub)
			wsp_sub_dat = wsp_sub.read()
			if wsp_sub_dat:
				parent = self.env['res.partner'].browse(wsp_sub.employer_id.id)
				# raise Warning(wsp_sub_dat)
				for field in wsp_sub_dat[0].keys():
					if type(wsp_sub_dat[0].get(field)) == tuple:
						wsp_sub_dat[0].update({field: wsp_sub_dat[0].get(field)[0]})
				for child in parent.child_employer_ids:
					ok = False
					child_partner = child.employer_id
					if child_partner.id != parent.id:

						for child_stat in child_partner.wsp_submission_ids:
							if child_stat.name == wsp_sub_dat[0].get('name'):
								msg += wsp_sub_dat[0].get('name') + str(child_partner) + str(child_stat.id) + str(wsp_sub) + '\n'
							else:
								ok = True
					if ok:
						# dbg(child_partner)
						wsp_sub_dat[0].update({'employer_id': child_partner.id})
						wsp_submission_data = status_env.create(wsp_sub_dat[0])
						# dbg(wsp_submission_data)
		dbg(msg)
