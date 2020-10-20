# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def check_duplicate_record(self):
        for rec in self:
            clause_1 = ['&', ('date_to', '<=', rec.date_to), ('date_to', '>=', rec.date_from)]
            clause_2 = ['&', ('date_from', '<=', rec.date_to), ('date_from', '>=', rec.date_from)]
            clause_3 = ['&', ('date_from', '<=', rec.date_from), '|', ('date_to', '=', False), ('date_to', '>=', rec.date_to)]
            clause_final = [('employee_id', '=', rec.employee_id.id), ('state', '=', 'done'), ('id', '!=', rec.id), '|', '|'] + clause_1 + clause_2 + clause_3
            rec_ids = self.search(clause_final)
            if len(rec_ids) % 2 == 0 and rec.credit_note:
                raise ValidationError(_('You already Refund payslip with same duration of "%s".Kindly check Once.'
                                        % (rec.employee_id.name + ' ' + rec.employee_id.last_name)))
            elif not len(rec_ids) % 2 == 0 and not rec.credit_note:
               raise ValidationError(_('You already generated payslip with same duration of "%s".Kindly check Once.'
                                        % (rec.employee_id.name + ' ' + rec.employee_id.last_name)))

    def send_payslip(self):
        if self.employee_id.work_email:
            template = self.env.ref('saudi_hr_payroll.send_payslip_mail', raise_if_not_found=False)
            template.send_mail(self.id)
            self.is_send = True
        else:
            raise UserError(_("Please Set %s's Email and Confirm Payslip.") % self.employee_id.name)

    def action_payslip_done(self):
        self.check_duplicate_record()
        if self.env.user.has_group('saudi_hr_payroll.group_send_payslip'):
            self.send_payslip()
        res = super(HrPayslip, self).action_payslip_done()
        for payslip in self:
            if payslip.move_id:
                payslip.move_id.branch_id = payslip.employee_id.branch_id.id
                line_vals = {'branch_id': payslip.employee_id.branch_id.id or False,
                            'analytic_tag_ids': [(6, 0, payslip.contract_id.analytic_tag_ids.ids)] or False}
                if payslip.contract_id.analytic_account_id:
                    line_vals.update({'analytic_account_id': payslip.contract_id.analytic_account_id.id or False})
                payslip.move_id.line_ids.write(line_vals)
        return res

    def _get_payment_days(self):
        for line in self:
            nb_of_days = (line.date_to - line.date_from).days + 1
            # We will set it to 30 as our calculation is based on 30 days for your company
            month = line.date_from.month
            if nb_of_days > 30 or month == 2 and nb_of_days in (28, 29):
                nb_of_days = 30
            line.payment_days = nb_of_days

    def _get_first_month_days(self):
        for line in self:
            if not line.employee_id.date_of_join:
                raise UserError(_("Please enter 'Joining Date' of Employee first!"))
            number_of_days = (line.date_to - line.employee_id.date_of_join).days + 1
            line.first_month_days = number_of_days

    payment_days = fields.Float(compute='_get_payment_days', string='Payment Day(s)')
    first_month_days = fields.Float(compute='_get_first_month_days', string='No of day(s)')
    is_send = fields.Boolean(default=False, store=True)

    def get_other_allowance_deduction(self, employee_id, date_from, date_to):
        domain = [('employee_id', '=', employee_id.id),
                  ('payslip_id', '=', False), ('state', 'in', ['done']),
                  ('date', '>=', date_from), ('date', '<=', date_to)]
        other_ids = self.env['other.hr.payslip'].search(domain)
        res = []
        if other_ids:
            alw_no_of_days = alw_no_of_hours = alw_percentage = alw_amt = 0.0
            ded_no_of_days = ded_no_of_hours = ded_percentage = ded_amt = 0.0

            other_input_lines = {}

            for other in other_ids:
                if other.operation_type == 'allowance':
                    if other.calc_type == 'amount':
                        alw_amt += other.amount
                        if 'OTHER_ALLOWANCE_AMOUNT' not in other_input_lines:
                            other_input_lines['OTHER_ALLOWANCE_AMOUNT'] = alw_amt
                        else:
                            other_input_lines.update({'OTHER_ALLOWANCE_AMOUNT': alw_amt})
                    elif other.calc_type == 'days':
                        alw_no_of_days += other.no_of_days
                        if 'OTHER_ALLOWANCE_DAYS' not in other_input_lines:
                            other_input_lines['OTHER_ALLOWANCE_DAYS'] = alw_no_of_days
                        else:
                            other_input_lines.update({'OTHER_ALLOWANCE_DAYS': alw_no_of_days})
                    elif other.calc_type == 'hours':
                        alw_no_of_hours += other.no_of_hours
                        if 'OTHER_ALLOWANCE_HOURS' not in other_input_lines:
                            other_input_lines['OTHER_ALLOWANCE_HOURS'] = alw_no_of_hours
                        else:
                            other_input_lines.update({'OTHER_ALLOWANCE_HOURS': alw_no_of_hours})
                    elif other.calc_type == 'percentage':
                        alw_percentage += other.percentage
                        if 'OTHER_ALLOWANCE_PERCENTAGE' not in other_input_lines:
                            other_input_lines['OTHER_ALLOWANCE_PERCENTAGE'] = alw_percentage
                        else:
                            other_input_lines.update({'OTHER_ALLOWANCE_PERCENTAGE': alw_percentage})

                elif other.operation_type == 'deduction':
                    if other.calc_type == 'amount':
                        ded_amt += other.amount
                        if 'OTHER_DEDUCTION_AMOUNT' not in other_input_lines:
                            other_input_lines['OTHER_DEDUCTION_AMOUNT'] = ded_amt
                        else:
                            other_input_lines.update({'OTHER_DEDUCTION_AMOUNT': ded_amt})
                    elif other.calc_type == 'days':
                        ded_no_of_days += other.no_of_days
                        if 'OTHER_DEDUCTION_DAYS' not in other_input_lines:
                            other_input_lines['OTHER_DEDUCTION_DAYS'] = ded_no_of_days
                        else:
                            other_input_lines.update({'OTHER_DEDUCTION_DAYS': ded_no_of_days})
                    elif other.calc_type == 'hours':
                        ded_no_of_hours += other.no_of_hours
                        if 'OTHER_DEDUCTION_HOURS' not in other_input_lines:
                            other_input_lines['OTHER_DEDUCTION_HOURS'] = ded_no_of_hours
                        else:
                            other_input_lines.update({'OTHER_DEDUCTION_HOURS': ded_no_of_hours})
                    elif other.calc_type == 'percentage':
                        ded_percentage += other.percentage
                        if 'OTHER_DEDUCTION_PERCENTAGE' not in other_input_lines:
                            other_input_lines['OTHER_DEDUCTION_PERCENTAGE'] = ded_percentage
                        else:
                            other_input_lines.update({'OTHER_DEDUCTION_PERCENTAGE': ded_percentage})

            for code, amount in other_input_lines.items():
                res.append({'code': code, 'amount': amount})
        return res

    @api.onchange('employee_id', 'struct_id', 'contract_id', 'date_from', 'date_to')
    def _onchange_employee(self):
        res = super()._onchange_employee()
        other_types = {
            'OTHER_ALLOWANCE_AMOUNT': self.env.ref('saudi_hr_payroll.other_allowance_amount_input').id,
            'OTHER_ALLOWANCE_DAYS': self.env.ref('saudi_hr_payroll.other_allowance_days_input').id,
            'OTHER_ALLOWANCE_HOURS': self.env.ref('saudi_hr_payroll.other_allowance_hours_input').id,
            'OTHER_ALLOWANCE_PERCENTAGE': self.env.ref('saudi_hr_payroll.other_allowance_percentage_input').id,
            'OTHER_DEDUCTION_AMOUNT': self.env.ref('saudi_hr_payroll.other_deduction_amount_input').id,
            'OTHER_DEDUCTION_DAYS': self.env.ref('saudi_hr_payroll.other_deduction_days_input').id,
            'OTHER_DEDUCTION_HOURS': self.env.ref('saudi_hr_payroll.other_deduction_hours_input').id,
            'OTHER_DEDUCTION_PERCENTAGE': self.env.ref('saudi_hr_payroll.other_deduction_percentage_input').id,
        }
        if not self.contract_id:
            lines_to_remove = self.input_line_ids.filtered(lambda x: x.input_type_id.id in other_types.values())
            self.update({'input_line_ids': [(3, line.id, False) for line in lines_to_remove]})

        other_allowance_data = self.get_other_allowance_deduction(self.employee_id, self.date_from, self.date_to)
        if other_allowance_data:
            lines_to_keep = self.input_line_ids.filtered(lambda x: x.input_type_id.id not in other_types.values())
            input_line_vals = [(5, 0, 0)] + [(4, line.id, False) for line in lines_to_keep]

            for other_type in other_allowance_data:
                if other_types.get(other_type['code']):
                    input_line_vals.append((0, 0, {
                        'amount': other_type['amount'],
                        'input_type_id': other_types[other_type['code']],
                    }))
            self.update({'input_line_ids': input_line_vals})
        return res


