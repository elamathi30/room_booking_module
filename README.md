# Room Booking Module

A standalone Odoo module for booking rooms and equipment with conflict prevention, availability windows, and lifecycle management.

## Features (Base Requirements - Complete)

✅ **CRUD on Bookings**: Full read, create, update, delete operations with proper access control  
✅ **Conflict Prevention**: Overlapping bookings are rejected with clear error messages  
✅ **Availability Windows**: Resources have configurable business hours (e.g., 9 AM - 6 PM)  
✅ **Booking Lifecycle**: 4-state workflow - Requested → Confirmed → Completed/Cancelled  
✅ **List View as Default**: Bookings and Resources accessible via tree views  
✅ **Data Model & UX**: Full design control over fields, views, and user flows  

## Design Decisions

### Core Models

**1. `room.booking.resource` (Resource Model)**
- Represents rooms, equipment, or any bookable resource
- Fields:
  - `name`: Resource name (e.g., "Conference Room A")
  - `resource_type`: Classification (Room, Equipment, Other)
  - `capacity`: How many people/units can use it
  - `availability_start` / `availability_end`: Business hours (as floats: 9.0 = 9 AM, 18.0 = 6 PM)
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

### Conflict Detection Strategy

**Location**: Constraints in `booking.py` (`_check_availability_and_conflicts`)

**Logic**:
1. **Availability Window Check**: Reject bookings outside resource's business hours
2. **Overlap Detection**: Use domain query to find conflicting bookings
   - Domain: `start_time < booking.end_time AND end_time > booking.start_time`
   - Filters: Only active bookings (`requested` or `confirmed` states), excludes cancelled/completed
   - When updating a booking, the existing booking ID is excluded to avoid self-conflict

**Why this approach**:
- Runs at the database constraint level (reliable, can't bypass)
- User-friendly error messages with conflict details
- Efficient: single database query

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
│Completed │  (finished, final state)
└──────────┘

┌──────────┐
│Requested │  (can also cancel before confirming)
└────┬─────┘
     │ action_cancel()
     ↓
┌──────────┐
│Cancelled │  (abandoned, final state)
└──────────┘
```

Transitions enforced by:
- Button visibility in form (state-based with `states="..."` attributes)
- Database state field tracks current status
- Activity log (mail.thread) records all transitions

### Access Control

**File**: `security/ir.model.access.csv`

Currently: **All authenticated users can CRUD bookings and resources**
- All users (no group restriction) have full permissions
- Can be refined later to restrict by role (e.g., Admin-only resource creation)

### UI/UX Design

**Resource Management**:
- List view: Quick overview of all resources, capacity, availability
- Form view: Edit resource details, set availability windows (with float widget for hours)

**Booking Management**:
- List view: Default view showing all bookings
- Form view: Full booking details with:
  - Status bar (visual state indicator)
  - Action buttons (Confirm, Complete, Cancel)
  - Chatter section for activity tracking and comments
  - Time picker for start/end times

**Search & Filters**:
- Quick filters: by state (Requested, Confirmed, Completed, Cancelled)
- Searchable: by booking reference, title, resource, user

## Bonus Feature: Odoo Integration

**Implemented**: Mail module integration (`mail.thread`, `mail.activity.mixin`)

- **Activity Tracking**: All state changes and notes appear in the chatter
- **Comments**: Users can add comments to bookings
- **Activity Log**: Built-in audit trail of who did what and when
- **Future**: Calendar integration (Day 5-6) can display bookings in Odoo Calendar

## Simplified/Left Out & Why

1. **Recurring Bookings**: Not included
   - Adds complexity to conflict detection (checking many dates)
   - Most room bookings are one-off; recurring can be handled manually
   - Can be added as enhancement using `rrule` library

2. **Resource Categories/Hierarchies**: Kept simple
   - Single resource type (not tree structure)
   - Sufficient for MVP; can extend with `parent_id` field if needed

3. **Approval Workflow**: No multi-level approvals
   - Simple 2-state (Requested → Confirmed) vs. complex routing
   - Adequate for internal team bookings
   - Can add manager approval using workflow engine if scaled

4. **Notifications/Reminders**: Not in base
   - Part of "Automation" bonus feature (will add in Day 6-7 if time)
   - Would need cron job + email templates

5. **Resource Maintenance/Blackout Dates**: Not included
   - Can be modeled as special "maintenance" bookings or a separate blackout_dates table
   - Deferred to V2

## Testing Notes

To test locally:
1. Install this module in your Odoo instance
2. Create a Resource (e.g., "Conference Room A", 9 AM - 6 PM)
3. Create a Booking (e.g., 10 AM - 11 AM on the same resource)
4. Try creating an overlapping booking → should fail with conflict message
5. Try booking outside availability (e.g., 8 PM) → should fail with window message
6. Confirm booking → lifecycle progresses
7. Add notes → appears in chatter

## File Structure

```
room_booking/
├── __init__.py                    # Module loader
├── __manifest__.py                # Metadata (name, dependencies, data files)
├── models/
│   ├── __init__.py
│   ├── resource.py                # Resource model + conflict/availability logic
│   └── booking.py                 # Booking model + lifecycle + constraints
├── views/
│   ├── resource_views.xml         # Resource list & form + menu
│   └── booking_views.xml          # Booking list, form, search + menu + actions
├── security/
│   └── ir.model.access.csv        # Access control (CRUD permissions)
└── README.md                       # This file
```

## Tech Stack

- **Framework**: Odoo 14+ (uses `mail.thread`, `mail.activity.mixin`)
- **Language**: Python 3.x
- **Database**: PostgreSQL (Odoo's default)
- **Frontend**: Odoo's built-in form/list/tree views (XML-based)

## Next Steps (If Continuing)

1. **Calendar View** (Bonus: Odoo Integration)
   - Inherit from `calendar.event` to show bookings in Odoo Calendar
   
2. **Automation** (Bonus: Scheduled Logic)
   - Cron job to auto-complete past bookings
   - Email reminders before booking start time

3. **AI Feature** (Bonus: AI-Powered)
   - Conflict resolution suggestions
   - Natural language booking entry
   - Usage analytics/reports

4. **Reporting**
   - Booking utilization by resource
   - User booking history
   - Peak hours analysis

## Author

Built as an Odoo internship exercise.

## License

LGPL-3.0
