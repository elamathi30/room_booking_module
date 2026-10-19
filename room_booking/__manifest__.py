# Module metadata and installation wiring.
# REQ: installable Odoo add-on; loads access rules, reference sequence,
# reminder configuration/template, and resource/booking UI.
# Odoo built-ins: base ORM, mail integration, XML data loader.

# so here we define the module metadata and installation wiring for Odoo to recognize and install this add-on.
#file is to tell all the class files we define for odoo to include in this modules and know how to integrate and use them 

{
    'name': 'Room Booking Module',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Manage room and equipment bookings with conflict prevention',
    'description': '''
        A standalone module for booking rooms and equipment with:
        - CRUD operations on bookings
        - Conflict prevention (overlapping bookings rejected)
        - Availability windows (business hours support)
        - Booking lifecycle (Requested → Confirmed → Completed/Cancelled)
        - List and form views
        - Email notifications for booking events
        - One-hour booking reminders and chatter-based notifications for upcoming bookings
    

    ''',
    'author': 'ela',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/mail_template.xml',
        'data/reminder_cron.xml',
        'views/resource_views.xml',
        'views/booking_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
