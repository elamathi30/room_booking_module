# Room Booking Resource Model
# Stores room/equipment details, capacity, availability hours, and linked bookings.

# Required validation logic:
# 1. Availability start must be >= 0.
# 2. Availability start must be earlier than availability end.
# 3. Availability end must be <= 24.
# 4. Capacity must be at least 1.

# Required conflict-checking logic:
# 5. Only check bookings for the same resource.
# 6. Only requested and confirmed bookings block the time slot.
# 7. Existing booking start_time < new booking end_time.
# 8. Existing booking end_time > new booking start_time.
#    Both conditions together detect overlapping time periods.
# 9. Exclude the current booking when checking an update.

# Required availability logic:
# 10. Convert booking datetimes from UTC to the chosen timezone.
# 11. Start and end must fall on the same local date.
# 12. Start hour must be >= resource availability_start.
# 13. End hour must be <= resource availability_end.

import pytz
from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Define the RoomBookingResource model for bookable rooms and equipment.

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

# Constraints and utility methods for resource availability and conflict checking
# Ensure that availability start is before availability end and capacity is positive.

    @api.constrains('availability_start', 'availability_end', 'capacity')
    def _check_resource_values(self):
        """Reject impossible hours and capacities so a resource can't silently block all bookings."""
        for resource in self:
            if not (0 <= resource.availability_start < resource.availability_end <= 24):
                raise ValidationError(
                    'Availability must start before it ends, within 00:00–24:00.'
                )
            if resource.capacity < 1:
                raise ValidationError('Capacity must be at least 1.')
# Check for overlapping bookings when creating or updating a booking.

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
        self.ensure_one()
        domain = [
            ('resource_id', '=', self.id),
            ('state', 'in', ['requested', 'confirmed']),
            ('start_time', '<', end_time),
            ('end_time', '>', start_time),
        ]

        if exclude_booking_id:
            domain.append(('id', '!=', exclude_booking_id))

        return self.env['room.booking.booking'].search(domain)
    
    # Check if a given booking time falls within the resource's availability window.
    def is_within_availability(self, start_time, end_time, tz_name=None):
        """
        Check if booking times fall within resource availability windows.

        Args:
            start_time: datetime when booking starts
            end_time: datetime when booking ends
            tz_name: timezone to evaluate the window in (defaults to UTC)

        Returns:
            True if within availability, False otherwise
        """
        self.ensure_one()
        tz = pytz.timezone(tz_name or 'UTC')
        start_time = pytz.utc.localize(start_time).astimezone(tz)
        end_time = pytz.utc.localize(end_time).astimezone(tz)
        if start_time.date() != end_time.date():
            return False
        start_hour = start_time.hour + (start_time.minute / 60.0)
        end_hour = end_time.hour + (end_time.minute / 60.0)

        return (start_hour >= self.availability_start and
                end_hour <= self.availability_end)