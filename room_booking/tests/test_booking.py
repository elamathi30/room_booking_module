# REQ coverage: automated checks for overlap and back-to-back times, time
# ordering, availability, lifecycle/cancellation, schedule colors, and
# one-time reminder activity/email integration. Uses Odoo TransactionCase.
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase


class TestRoomBooking(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.tz = 'Asia/Manila'
        cls.env = cls.env(user=cls.admin)
        cls.resource = cls.env['room.booking.resource'].create({
            'name': 'Test Conference Room',
            'availability_start': 9.0,
            'availability_end': 18.0,
        })
        cls.booking_model = cls.env['room.booking.booking']

    def _create_booking(self, start='2099-01-01 01:00:00', end='2099-01-01 02:00:00'):
        return self.booking_model.create({
            'title': 'Test booking',
            'resource_id': self.resource.id,
            'start_time': start,
            'end_time': end,
        })

    def test_overlapping_booking_is_rejected_and_back_to_back_is_allowed(self):
        self._create_booking()
        with self.assertRaisesRegex(ValidationError, 'overlaps booking'):
            with self.cr.savepoint():
                self._create_booking('2099-01-01 01:30:00', '2099-01-01 02:30:00')

        next_booking = self._create_booking('2099-01-01 02:00:00', '2099-01-01 03:00:00')
        self.assertEqual(next_booking.duration_hours, 1.0)

    def test_invalid_order_is_rejected_and_has_no_negative_duration(self):
        with self.assertRaisesRegex(ValidationError, 'End time must be later'):
            with self.cr.savepoint():
                self._create_booking('2099-01-01 03:00:00', '2099-01-01 02:30:00')

        draft = self.booking_model.new({
            'start_time': '2099-01-01 03:00:00',
            'end_time': '2099-01-01 02:30:00',
        })
        self.assertEqual(draft.duration_hours, 0.0)
        self.assertEqual(
            draft.validation_message,
            'End time must be later than start time.',
        )

    def test_outside_availability_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, 'outside this resource'):
            with self.cr.savepoint():
                self._create_booking('2099-01-01 00:00:00', '2099-01-01 01:00:00')

    def test_completion_is_blocked_until_after_end_time(self):
        booking = self._create_booking()
        booking.action_confirm()
        with self.assertRaisesRegex(ValidationError, 'only after its scheduled end time'):
            booking.action_complete()

    def test_completed_booking_can_only_be_completed_after_its_end(self):
        end_time = fields.Datetime.now().replace(
            hour=2, minute=0, second=0, microsecond=0
        ) - timedelta(days=1)
        start_time = end_time - timedelta(hours=1)
        booking = self._create_booking(
            fields.Datetime.to_string(start_time),
            fields.Datetime.to_string(end_time),
        )
        booking.action_confirm()
        booking.action_complete()
        self.assertEqual(booking.state, 'completed')

    def test_cancellation_requires_and_records_a_reason(self):
        booking = self._create_booking()
        with self.assertRaisesRegex(ValidationError, 'cancellation reason is required'):
            booking.write({'state': 'cancelled'})

        wizard = self.env['room.booking.cancel.wizard'].create({
            'booking_id': booking.id,
            'reason': '  Meeting was postponed.  ',
        })
        wizard.action_confirm_cancel()
        self.assertEqual(booking.state, 'cancelled')
        self.assertEqual(booking.cancellation_reason, 'Meeting was postponed.')

    def test_terminal_state_cannot_be_reopened(self):
        end_time = fields.Datetime.now().replace(
            hour=2, minute=0, second=0, microsecond=0
        ) - timedelta(days=1)
        start_time = end_time - timedelta(hours=1)
        booking = self._create_booking(
            fields.Datetime.to_string(start_time),
            fields.Datetime.to_string(end_time),
        )
        booking.action_confirm()
        booking.action_complete()
        with self.assertRaisesRegex(ValidationError, 'Cannot change a booking'):
            booking.write({'state': 'confirmed'})

    def test_internal_users_only_change_their_own_bookings(self):
        booking = self._create_booking()
        user = self.env['res.users'].create({
            'name': 'Plain User',
            'login': 'plain_booking_user',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        as_user = booking.with_user(user)
        self.assertEqual(as_user.title, 'Test booking')
        with self.assertRaises(AccessError):
            as_user.write({'title': 'Hijacked'})
        with self.assertRaises(AccessError):
            as_user.unlink()
        with self.assertRaises(AccessError):
            self.env['room.booking.resource'].with_user(user).create({'name': 'Nope'})

        own = self.booking_model.with_user(user).create({
            'title': 'Mine',
            'resource_id': self.resource.id,
            'start_time': '2099-02-01 10:00:00',
            'end_time': '2099-02-01 11:00:00',
        })
        own.write({'title': 'Mine edited'})
        own.unlink()

    def test_schedule_colors_match_booking_states(self):
        expected_colors = {
            'requested': '#f8d7da',
            'confirmed': '#e4d9f5',
            'completed': '#e9ecef',
            'cancelled': '#e9ecef',
        }
        for state, color in expected_colors.items():
            booking = self.booking_model.new({'state': state})
            self.assertEqual(booking.calendar_color, color)

    def test_confirmed_booking_gets_one_hour_reminder_once(self):
        booking = self._create_booking(
            '2099-01-01 02:00:00',
            '2099-01-01 03:00:00',
        )
        booking.user_id = self.admin
        booking.user_id.notification_type = 'inbox'
        booking.action_confirm()
        reminder_time = datetime(2099, 1, 1, 1, 5)

        with patch.object(type(self.env['mail.mail']), 'send', autospec=True) as mail_send:
            self.booking_model.sudo()._cron_send_booking_reminders(now=reminder_time)
            mail_send.assert_called_once()

        booking.invalidate_recordset()
        self.assertTrue(booking.reminder_sent)
        self.assertEqual(booking.reminder_sent_at, reminder_time)
        activity = self.env['mail.activity'].search([
            ('res_model', '=', booking._name),
            ('res_id', '=', booking.id),
            ('summary', '=', 'Upcoming room booking'),
        ], limit=1)
        self.assertTrue(activity)
        self.assertEqual(
            activity.date_deadline,
            fields.Date.context_today(booking.with_context(tz=booking.user_id.tz)),
        )
        self.assertEqual(
            self.env['mail.activity'].search_count([
                ('res_model', '=', booking._name),
                ('res_id', '=', booking.id),
                ('summary', '=', 'Upcoming room booking'),
            ]),
            1,
        )
        self.assertEqual(
            self.env['mail.mail'].search_count([
                ('email_to', 'ilike', self.admin.email),
                ('subject', 'ilike', booking.title),
            ]),
            1,
        )

        self.booking_model.sudo()._cron_send_booking_reminders(now=reminder_time)
        self.assertEqual(
            self.env['mail.activity'].search_count([
                ('res_model', '=', booking._name),
                ('res_id', '=', booking.id),
                ('summary', '=', 'Upcoming room booking'),
            ]),
            1,
        )
