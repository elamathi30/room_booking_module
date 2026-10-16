import pytz
from odoo import models, fields


class RoomBookingResource(models.Model):
    _name = 'room.booking.resource'
    _description = 'Room/Equipment Resource'
    _rec_name = 'name'

    name = fields.Char(
        string='Resource Name',
        required=True,
        help='Name of the room or equipment (e.g., "Conference Room A")'
    )
    
    resource_type = fields.Selection(
        [
            ('room', 'Room'),
            ('equipment', 'Equipment'),
            ('other', 'Other')
        ],
        string='Type',
        required=True,
        default='room',
        help='Classify the resource'
    )
    
    capacity = fields.Integer(
        string='Capacity',
        default=1,
        help='Max number of people or usage units'
    )
    
    description = fields.Text(
        string='Description',
        help='Details about this resource'
    )
    
    availability_start = fields.Float(
        string='Available From (Hour)',
        default=9.0,
        help='Availability window start (e.g., 9.0 = 9 AM)'
    )
    
    availability_end = fields.Float(
        string='Available Until (Hour)',
        default=18.0,
        help='Availability window end (e.g., 18.0 = 6 PM)'
    )
    
    is_available = fields.Boolean(
        string='Is Available',
        default=True,
        help='Mark resource as available/unavailable'
    )
    
    booking_ids = fields.One2many(
        'room.booking.booking',
        'resource_id',
        string='Bookings',
        help='All bookings for this resource'
    )
    
    def get_conflicts(self, start_time, end_time, exclude_booking_id=None):
        """
        Find overlapping bookings for this resource.
        
        Args:
            start_time: datetime when booking starts
            end_time: datetime when booking ends
            exclude_booking_id: booking ID to exclude (useful for updates)
        
        Returns:
            Recordset of conflicting bookings
        """
        domain = [
            ('resource_id', '=', self.id),
            ('state', 'in', ['requested', 'confirmed']),
            ('start_time', '<', end_time),
            ('end_time', '>', start_time),
        ]
        
        if exclude_booking_id:
            domain.append(('id', '!=', exclude_booking_id))
        
        return self.env['room.booking.booking'].search(domain)
    
    def is_within_availability(self, start_time, end_time, tz_name=None):
        """
        Check if booking times fall within resource availability windows.
        
        Args:
            start_time: datetime when booking starts
            end_time: datetime when booking ends
        
        Returns:
            True if within availability, False otherwise
        """
        tz = pytz.timezone(tz_name or 'UTC')
        start_time = pytz.utc.localize(start_time).astimezone(tz)
        end_time = pytz.utc.localize(end_time).astimezone(tz)
        if start_time.date() != end_time.date():
            return False
        start_hour = start_time.hour + (start_time.minute / 60.0)
        end_hour = end_time.hour + (end_time.minute / 60.0)
        
        return (start_hour >= self.availability_start and 
                end_hour <= self.availability_end)
