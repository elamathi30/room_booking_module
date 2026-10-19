
# Cancellation Wizard
# Uses Odoo's TransientModel to provide a temporary cancellation form.
# booking_id links the wizard to the booking being cancelled.
# reason is required and must contain non-whitespace characters.

# Cancellation logic:
# 1. ensure_one() ensures only one wizard record is processed.
# 2. (self.reason or '').strip() handles an empty value and removes surrounding spaces.
# 3. If the cleaned reason is empty, raise ValidationError and stop cancellation.
# 4. If valid, update the booking's state to 'cancelled' and save the reason.
# 5. Close the wizard after the booking is updated.

from odoo import fields, models
from odoo.exceptions import ValidationError

# Wizard for cancelling a room booking with a mandatory reason.
class RoomBookingCancelWizard(models.TransientModel):
    _name = 'room.booking.cancel.wizard'
    _description = 'Cancel Room Booking'

    booking_id = fields.Many2one(
        'room.booking.booking',
        string='Booking',
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string='Cancellation Reason',
        required=True,
    )
    # Action to confirm the cancellation of the booking.
    def action_confirm_cancel(self):
        self.ensure_one()
        reason = (self.reason or '').strip()
        if not reason:
            raise ValidationError('Please provide a cancellation reason.')
        self.booking_id.write({
            'state': 'cancelled',
            'cancellation_reason': reason,
        })
        return {'type': 'ir.actions.act_window_close'}
