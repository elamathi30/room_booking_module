from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime


class RoomBookingBooking(models.Model):
    _name = 'room.booking.booking'
    _description = 'Room Booking'
    _rec_name = 'booking_reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    booking_reference = fields.Char(
        string='Booking Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('room.booking.booking') or 'New',
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
        track_visibility='onchange',
        help='Booking lifecycle state'
    )
    
    notes = fields.Text(
        string='Notes',
        track_visibility='onchange',
        help='Internal notes about the booking'
    )
    
    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        """Calculate booking duration in hours."""
        for booking in self:
            if booking.start_time and booking.end_time:
                delta = booking.end_time - booking.start_time
                booking.duration_hours = delta.total_seconds() / 3600
            else:
                booking.duration_hours = 0.0
    
    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        """Ensure end_time is after start_time."""
        for booking in self:
            if booking.start_time and booking.end_time:
                if booking.end_time <= booking.start_time:
                    raise ValidationError(
                        'End time must be after start time.'
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
            
            resource = booking.resource_id
            
            if not resource.is_available:
                raise ValidationError(
                    f'Resource "{resource.name}" is currently unavailable.'
                )
            
            if not resource.is_within_availability(booking.start_time, booking.end_time):
                raise ValidationError(
                    f'Booking time {booking.start_time} to {booking.end_time} '
                    f'is outside resource availability hours '
                    f'({resource.availability_start:.0f}:00 - {resource.availability_end:.0f}:00).'
                )
            
            conflicts = resource.get_conflicts(
                booking.start_time,
                booking.end_time,
                exclude_booking_id=booking.id if booking.id else None
            )
            
            if conflicts:
                conflict_details = ', '.join([
                    f"{c.booking_reference} ({c.start_time} - {c.end_time})"
                    for c in conflicts
                ])
                raise ValidationError(
                    f'Booking conflicts with existing reservations: {conflict_details}'
                )
    
    def action_confirm(self):
        """Transition booking from Requested to Confirmed."""
        self.write({'state': 'confirmed'})
    
    def action_complete(self):
        """Transition booking from Confirmed to Completed."""
        self.write({'state': 'completed'})
    
    def action_cancel(self):
        """Transition booking to Cancelled."""
        self.write({'state': 'cancelled'})
