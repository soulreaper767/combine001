{
    'name': 'Combine001',
    'version': '19.0.1.0.0',
    'category': 'Uncategorized',
    'summary': 'Combine001 custom app',
    'description': """
Combine001
==========
Starter skeleton for the Combine001 custom app.
""",
    'author': 'Sibyl Technologies',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/combine001_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
