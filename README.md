# Room Booking Module

A standalone Odoo module for booking rooms and equipment with conflict prevention, availability windows, and lifecycle management.

## Implementation Map: Requirements, Odoo, and Tools

This map explains which module file covers each documented requirement, what is
custom code versus Odoo-provided behavior, and the implementation technology.

| Requirement / feature | Implemented in | What this module adds | Odoo built-in / technology |
|---|---|---|---|
| Manage rooms and equipment, including availability hours | `models/resource.py`, `views/resource_views.xml` | Custom resource model, resource types, capacity, availability switch and daily hours; list/form screens | Odoo ORM fields and CRUD; XML views |
| Create and manage bookings, calculate duration and assign references | `models/booking.py`, `data/sequence.xml` | Custom booking model, generated `BK/` reference, owner/resource/time fields and computed duration | Odoo ORM and `ir.sequence`; Python |
| Prevent invalid times, out-of-hours bookings and overlapping reservations | `models/booking.py`, `models/resource.py` | Custom validation, user-timezone availability checks and overlap detection for requested/confirmed bookings | Odoo model constraints and `ValidationError`; Python / ORM search |
| Booking lifecycle and required cancellation reason | `models/booking.py`, `models/cancel_wizard.py`, `views/booking_views.xml` | Custom state transitions and completion timing; cancellation dialog requires and stores a reason | Odoo `TransientModel`, form actions and status bar; Python / XML |
| Booking/resource list and form screens, search and state filters | `views/booking_views.xml`, `views/resource_views.xml` | Custom menus, screens and search filters | Odoo actions, menus, list/form/search views; XML |
| Schedule view, resource filtering and state colors | `views/booking_views.xml`, `models/booking.py` | Custom calendar action over booking records; filters by resource and maps state to a color value | Odoo calendar view; XML / Python |
| Track changes, comments and upcoming reminders (extra Odoo integration) | `models/booking.py`, `data/reminder_cron.xml`, `data/mail_template.xml` | Uses Odoo chatter/activity APIs; custom five-minute job schedules a one-hour reminder once per confirmed booking | Odoo `mail.thread`, `mail.activity.mixin`, mail activities, templates and `ir.cron`; Python / XML |
| Read/write/create/delete access control | `security/security.xml`, `security/ir.model.access.csv` | Room Booking Manager group; internal users read resources and all bookings but create/edit/delete only their own bookings; only managers (and administrators) manage resources and others' bookings | Odoo `res.groups`, `ir.rule`, model access CSV (CSV must keep its header first) |
| Run and locally test the Odoo module and reminder email capture | `docker-compose.yml`, `tests/test_booking.py` | Local Odoo/PostgreSQL/Mailpit services and automated model tests | Docker Compose, Odoo `TransactionCase`, PostgreSQL, Mailpit |

**What is built in versus custom:** Odoo supplies the ORM, PostgreSQL persistence,
record CRUD framework, access-control engine, list/form/search/calendar view
widgets, actions/menus, sequences, mail tracking/activities, templates and
scheduled-job runner. This module supplies the booking/resource models and
business rules, the booking workflow and cancellation wizard, its XML screens,
the reminder job/template configuration and access entries. It does not create
duplicate events in Odoo's separate Calendar app; the schedule displays these
module's booking records in Odoo's calendar view.

## Features (Base Requirements - Complete)

✅ **CRUD on Bookings**: Full read, create, update, delete operations with proper access control  
✅ **Conflict Prevention**: Overlapping bookings are rejected with clear error messages  
✅ **Availability Windows**: Resources have configurable business hours (e.g., 9 AM - 6 PM)  
✅ **Booking Lifecycle**: 4-state workflow - Requested → Confirmed → Completed/Cancelled  
✅ **List View as Default**: Bookings and Resources accessible via list views  
✅ **Data Model & UX**: Full design control over fields, views, and user flows  
✅ **Schedule**: Week/day/month calendar view of bookings, filterable by resource and color-coded by status
✅ **One-hour Reminders**: Confirmed bookings generate an Odoo activity and a reminder notification through the booking owner's chosen Odoo notification channel

## Design Decisions

### Core Models

**1. `room.booking.resource` (Resource Model)**
- Represents rooms, equipment, or any bookable resource
- Fields:
  - `name`: Resource name (e.g., "Conference Room A")
  - `resource_type`: Classification (Room, Equipment, Other)
  - `capacity`: How many people/units can use it
  - `availability_start` / `availability_end`: Business hours (stored as floats, displayed as times such as 9:00 and 18:00)
  - `is_available`: Boolean flag to disable resource temporarily
  - `booking_ids`: One2many relationship to bookings

**2. `room.booking.booking` (Booking Model)** 
- Represents a specific booking request
- Inherits from `mail.thread` for activity tracking (bonus feature: Odoo integration)
- Fields:
  - `booking_reference`: Auto-generated unique ID (sequential)
  - `user_id`: Who booked it
  - `resource_id`: Which resource
  - `start_time` / `end_time`: Booking timeframe
  - `duration_hours`: Computed field (readonly)
  - `title` / `description`: Purpose and details
  - `state`: Lifecycle state (requested, confirmed, completed, cancelled)
  - `notes`: Internal tracking (tracked in chatter)
  - `cancellation_reason`: Required reason recorded when a booking is cancelled

### Conflict Detection Strategy

**Location**: Booking validation in `booking.py`

**Logic**:
1. **Availability Window Check**: Reject bookings outside resource's business hours
2. **Overlap Detection**: Use domain query to find conflicting bookings
   - Domain: `start_time < booking.end_time AND end_time > booking.start_time`
   - Filters: Only active bookings (`requested` or `confirmed` states), excludes cancelled/completed
   - When updating a booking, the existing booking ID is excluded to avoid self-conflict

**Why this approach**:
- Validation is shown inline while editing and checked again by server-side constraints when saving
- Conflict messages show the other booking's time in the current user's timezone
- A single database query finds overlapping active bookings

### Booking Lifecycle

States and transitions:
```
┌──────────┐
│Requested │  (initial state when created)
└────┬─────┘
     │ action_confirm()
     ↓
┌──────────┐
│Confirmed │  (approved, will proceed)
└────┬─────┘
     │ action_complete()
     ↓
┌──────────┐
│Completed │  (booking has ended and was actually used)
└──────────┘

┌──────────┐
│Requested │  (can also cancel before confirming)
└────┬─────┘
     │ Provide cancellation reason
     ↓
┌──────────┐
│Cancelled │  (abandoned, final state)
└──────────┘
```

Transitions enforced by:
- Only valid state transitions are accepted by the model
- Completion is available only after the scheduled end time
- Cancellation requires a reason in a confirmation dialog
- Activity log (`mail.thread`) records state changes

### Access Control

**Files**: `security/security.xml`, `security/ir.model.access.csv`

- **Internal users**: read all resources and bookings (needed for conflict checks and the schedule); create bookings; edit/cancel/delete only their own (record rule on `user_id`)
- **Room Booking Manager** (implied for Administrators): full CRUD on resources and on every booking
- Portal/public users get no access
- Trade-off: no per-resource approver or department scoping

### UI/UX Design

**Resource Management**:
- List view: Quick overview of all resources, capacity, availability
- Form view: Edit resource details, set availability windows (with float widget for hours)

**Booking Management**:
- List view: Default view showing all bookings
- Form view: Full booking details with:
  - Status bar (visual state indicator)
  - Inline red validation feedback for invalid times, unavailable resources, and conflicts
  - Action buttons (Confirm when valid, Complete after end time, Cancel with a required reason)
  - Chatter section for activity tracking and comments
  - Time picker for start/end times

**Schedule**:
- Separate Schedule menu opens a native Odoo calendar view, defaulting to the week
- Filter bookings by room/resource using the calendar filter panel
- Creating from the calendar opens the full booking form so a resource must be selected
- Requested bookings are red, confirmed bookings light purple, and completed bookings gray
- Cancelled bookings are hidden from the schedule but remain available in the Bookings list
- The calendar displays the booking model directly; it does not create duplicate events in Odoo's separate Calendar app

**Search & Filters**:
- Quick filters: by state (Requested, Confirmed, Completed, Cancelled)
- Searchable: by booking reference, title, resource, user

## Bonus Feature: Odoo Integration

**Implemented**: Mail module integration (`mail.thread`, `mail.activity.mixin`)

- **Activity Tracking**: All state changes and notes appear in the chatter
- **Comments**: Users can add comments to bookings
- **Activity Log**: Built-in audit trail of who did what and when
- **Upcoming Reminder**: A five-minute scheduled job checks for confirmed bookings starting within an hour and reminds the booking owner once. The assigned Odoo activity creates the in-app notification or email according to that user's notification preferences. Users who selected **Handle in Odoo** also receive the dedicated reminder email; users who selected email receive Odoo's activity notification email only, avoiding duplicates.
- **Local Email Testing**: Docker Compose starts Mailpit at `http://localhost:8025`. Configure the local Odoo database's outgoing mail server to use host `mailpit`, port `1025`, leave the username and password empty, and use no connection encryption. This captures email locally and does not deliver it to real recipients. Configure this only in the local test database. The local `admin` test user is set to **Handle in Odoo** so you can see the Discuss notification as well as the email.
- **Schedule**: A separate calendar view shows the same booking records by day, week, or month

## Simplified/Left Out & Why

- **Recurring bookings**: Bookings are individual reservations; recurrence rules
  would add complexity to conflict checking.
- **Resource hierarchy**: Resources have a simple type, but no parent/child
  structure; that is unnecessary for the current scope.
- **Multi-step approvals**: Bookings use a single Requested → Confirmed flow,
  which is sufficient for a small internal team.
- **Maintenance/blackout dates**: There is no separate way to block a resource
  without creating a booking.
- **AI-assisted booking**: Not implemented; it would require an external AI
  service and is outside the scope of this module.

## Testing Notes

Automated Odoo `TransactionCase` tests are in `room_booking/tests/test_booking.py`.
They cover overlapping and back-to-back bookings, invalid time order and
duration, availability hours, completion timing, cancellation reasons, terminal
state transitions, access control, schedule colors, and one-time reminders
(activity and email). These are implemented test cases; no code-coverage
percentage has been measured.

For a manual smoke test, install the module, create a resource and booking, then
check conflict and availability validation, confirm/complete/cancel actions,
chatter notes, and the reminder activity/email. The reminder job runs every
five minutes and targets confirmed bookings starting within the next hour.

## File Structure

```
room_booking/
├── __init__.py                    # Module loader
├── __manifest__.py                # Metadata (name, dependencies, data files)
├── models/
│   ├── __init__.py
│   ├── resource.py                # Resource model + conflict/availability logic
│   └── booking.py                 # Booking model + lifecycle + constraints
│   └── cancel_wizard.py           # Required-reason cancellation dialog
├── views/
│   ├── resource_views.xml         # Resource list & form + menu
│   └── booking_views.xml          # Booking list, form, search, schedule + menus/actions
├── security/
│   └── ir.model.access.csv        # Access control (CRUD permissions)
├── tests/
│   └── test_booking.py            # Booking validation and lifecycle tests
└── README.md                       # This file
```

## Tech Stack

- **Framework**: Odoo 18 (uses `mail.thread`, `mail.activity.mixin`)
- **Language**: Python 3.x
- **Database**: PostgreSQL (Odoo's default)
- **Frontend**: Odoo's built-in form/list views (XML-based)
