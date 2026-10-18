# REQ: cancellation must collect a non-blank reason and record it with the
# cancelled state. Custom Python wizard using Odoo's built-in TransientModel.
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
