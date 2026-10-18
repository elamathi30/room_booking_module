# REQ: booking CRUD/data, generated references, duration, availability and
# overlap validation, lifecycle transitions, and one-hour reminders.
# Custom Python rules run on Odoo ORM/constraints; Odoo mail mixins, activities,
# sequence, and scheduled-job APIs provide the integration points.
import logging
from datetime import timedelta

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_datetime


_logger = logging.getLogger(__name__)


class RoomBookingBooking(models.Model):
    REMINDER_LEAD_TIME = timedelta(hours=1)

    _name = 'room.booking.booking'
    _description = 'Room Booking'
    _rec_name = 'booking_reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    booking_reference = fields.Char(
        string='Booking Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        help='Unique booking identifier'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Booked By',
        required=True,
        default=lambda self: self.env.user,
        help='User who created the booking'
    )
    
    resource_id = fields.Many2one(
        'room.booking.resource',
        string='Resource',
        required=True,
        help='Room or equipment to book'
    )
    
    start_time = fields.Datetime(
        string='Start Time',
        required=True,
        help='When the booking starts'
    )
    
    end_time = fields.Datetime(
        string='End Time',
        required=True,
        help='When the booking ends'
    )
    
    duration_hours = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration',
        store=True,
        help='Calculated booking duration'
    )

    validation_message = fields.Char(
        string='Booking Validation',
        compute='_compute_validation_message',
    )
    can_complete = fields.Boolean(
        compute='_compute_can_complete',
    )
    can_confirm = fields.Boolean(
        compute='_compute_can_confirm',
    )
    can_cancel = fields.Boolean(
        compute='_compute_can_cancel',
    )
    calendar_color = fields.Char(
        compute='_compute_calendar_color',
    )
    
    title = fields.Char(
        string='Booking Title',
        required=True,
        help='Brief description of the booking purpose'
    )
    
    description = fields.Text(
        string='Description',
        help='Additional details about the booking'
    )
    
    state = fields.Selection(
        [
            ('requested', 'Requested'),
            ('confirmed', 'Confirmed'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        required=True,
        default='requested',
        tracking=True,
        help='Booking lifecycle state'
    )
    
    notes = fields.Text(
        string='Notes',
        tracking=True,
        help='Internal notes about the booking'
    )

    cancellation_reason = fields.Text(
        string='Cancellation Reason',
        readonly=True,
        copy=False,
        tracking=True,
    )
    reminder_sent = fields.Boolean(
        string='Reminder Sent',
        readonly=True,
        copy=False,
        default=False,
    )
    reminder_sent_at = fields.Datetime(
        string='Reminder Sent At',
        readonly=True,
        copy=False,
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('booking_reference', 'New') == 'New':
                vals['booking_reference'] = (
                    self.env['ir.sequence'].next_by_code('room.booking.booking') or 'New'
                )
        return super().create(vals_list)

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        """Calculate booking duration in hours."""
        for booking in self:
            if booking.start_time and booking.end_time:
                delta = booking.end_time - booking.start_time
                booking.duration_hours = max(0.0, delta.total_seconds() / 3600)
            else:
                booking.duration_hours = 0.0

    @api.depends(
        'start_time',
        'end_time',
        'resource_id',
        'resource_id.is_available',
        'resource_id.availability_start',
        'resource_id.availability_end',
        'resource_id.booking_ids.start_time',
        'resource_id.booking_ids.end_time',
        'resource_id.booking_ids.state',
    )
    def _compute_validation_message(self):
        for booking in self:
            booking.validation_message = booking._get_validation_message()

    @api.depends('state', 'end_time')
    def _compute_can_complete(self):
        now = fields.Datetime.now()
        for booking in self:
            booking.can_complete = (
                bool(booking.id)
                and booking.state == 'confirmed'
                and booking.end_time
                and booking.end_time <= now
            )

    @api.depends('state', 'validation_message')
    def _compute_can_confirm(self):
        for booking in self:
            booking.can_confirm = (
                bool(booking.id)
                and booking.state == 'requested'
                and not booking.validation_message
            )

    @api.depends('state')
    def _compute_can_cancel(self):
        for booking in self:
            booking.can_cancel = (
                bool(booking.id) and booking.state in ('requested', 'confirmed')
            )

    @api.depends('state')
    def _compute_calendar_color(self):
        colors = {
            'requested': '#f8d7da',
            'confirmed': '#e4d9f5',
            'completed': '#e9ecef',
            'cancelled': '#e9ecef',
        }
        for booking in self:
            booking.calendar_color = colors[booking.state]

    @staticmethod
    def _format_availability_hour(hour):
        total_minutes = round(hour * 60)
        return f'{total_minutes // 60:02d}:{total_minutes % 60:02d}'

    def _get_validation_message(self):
        self.ensure_one()
        if not self.start_time or not self.end_time:
            return False
        if self.end_time <= self.start_time:
            return 'End time must be later than start time.'
        if not self.resource_id:
            return False

        resource = self.resource_id
        if not resource.is_available:
            return f'Resource "{resource.name}" is currently unavailable.'

        if not resource.is_within_availability(
            self.start_time, self.end_time, self.env.user.tz
        ):
            start = self._format_availability_hour(resource.availability_start)
            end = self._format_availability_hour(resource.availability_end)
            return (
                f'The selected time is outside this resource’s availability '
                f'({start}–{end}). Choose another time.'
            )

        conflicts = resource.get_conflicts(
            self.start_time,
            self.end_time,
            exclude_booking_id=self.id or None,
        )
        if conflicts:
            conflict = conflicts[0]
            conflict_start = format_datetime(
                self.env, conflict.start_time, tz=self.env.user.tz, dt_format='short'
            )
            conflict_end = format_datetime(
                self.env, conflict.end_time, tz=self.env.user.tz, dt_format='short'
            )
            return (
                f'This time overlaps booking {conflict.booking_reference}, '
                f'scheduled from {conflict_start} to {conflict_end}. '
                'Choose another time or resource.'
            )
        return False

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        """Ensure end_time is after start_time."""
        for booking in self:
            if booking.start_time and booking.end_time:
                if booking.end_time <= booking.start_time:
                    raise ValidationError(
                        'End time must be later than start time.'
                    )
    
    @api.constrains('start_time', 'end_time', 'resource_id')
    def _check_availability_and_conflicts(self):
        """
        Validate booking against:
        1. Resource availability windows (business hours)
        2. Existing bookings (conflict prevention)
        """
        for booking in self:
            if not booking.resource_id or not booking.start_time or not booking.end_time:
                continue
            message = booking._get_validation_message()
            if message:
                raise ValidationError(message)

    def write(self, vals):
        if 'state' in vals:
            allowed_transitions = {
                'requested': {'confirmed', 'cancelled'},
                'confirmed': {'completed', 'cancelled'},
                'completed': set(),
                'cancelled': set(),
            }
            for booking in self:
                if vals['state'] not in allowed_transitions[booking.state]:
                    raise ValidationError(
                        f'Cannot change a booking from '
                        f'{booking.state} to {vals["state"]}.'
                    )
                if vals['state'] == 'completed':
                    end_time = vals.get('end_time', booking.end_time)
                    if not end_time or end_time > fields.Datetime.now():
                        raise ValidationError(
                            'A booking can be completed only after its scheduled end time.'
                        )
                if vals['state'] == 'cancelled' and not vals.get(
                    'cancellation_reason', booking.cancellation_reason
                ):
                    raise ValidationError(
                        'A cancellation reason is required.'
                    )
        return super().write(vals)

    def action_confirm(self):
        """Transition booking from Requested to Confirmed."""
        for booking in self:
            message = booking._get_validation_message()
            if message:
                raise ValidationError(message)
        self.write({'state': 'confirmed'})

    @api.model
    def _cron_send_booking_reminders(self, now=None):
        """Notify confirmed booking owners one hour before their booking."""
        now = now or fields.Datetime.now()
        cutoff = now + self.REMINDER_LEAD_TIME
        bookings = self.search([
            ('state', '=', 'confirmed'),
            ('reminder_sent', '=', False),
            ('start_time', '>', now),
            ('start_time', '<=', cutoff),
        ], order='start_time, id')
        template = self.env.ref('room_booking.mail_template_booking_reminder')
        for booking in bookings:
            local_start = format_datetime(
                booking.env, booking.start_time, tz=booking.user_id.tz
            )
            local_end = format_datetime(
                booking.env, booking.end_time, tz=booking.user_id.tz
            )
            note = (
                f'{booking.title} at {booking.resource_id.name} is scheduled '
                f'from {local_start} to {local_end}.'
            )
            booking.activity_schedule(
                act_type_xmlid='mail.mail_activity_data_todo',
                date_deadline=fields.Date.context_today(
                    booking.with_context(tz=booking.user_id.tz)
                ),
                summary='Upcoming room booking',
                note=note,
                user_id=booking.user_id.id,
                automated=False,
            )
            if booking.user_id.notification_type == 'inbox' and booking.user_id.email:
                template.send_mail(
                    booking.id,
                    force_send=True,
                    raise_exception=True,
                )
            elif not booking.user_id.email:
                _logger.warning(
                    'Skipped room booking reminder email for %s: user %s has no email address.',
                    booking.booking_reference,
                    booking.user_id.display_name,
                )
            booking.write({
                'reminder_sent': True,
                'reminder_sent_at': now,
            })
    
    def action_complete(self):
        """Transition booking from Confirmed to Completed."""
        self.write({'state': 'completed'})
    
    def action_cancel(self):
        """Open the cancellation-reason dialog."""
        self.ensure_one()
        if self.state not in ('requested', 'confirmed'):
            raise ValidationError('Only requested or confirmed bookings can be cancelled.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Cancel Booking',
            'res_model': 'room.booking.cancel.wizard',
            'view_mode': 'form',
            'views': [(self.env.ref(
                'room_booking.room_booking_cancel_wizard_view_form'
            ).id, 'form')],
            'target': 'new',
            'context': {'default_booking_id': self.id},
        }
