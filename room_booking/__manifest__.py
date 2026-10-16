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
    ''',
    'author': 'Your Name',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/resource_views.xml',
        'views/booking_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
