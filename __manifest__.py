{
    'name': 'CTL',
    'version': '1.0',
    'summary': 'Odoo module for CTL customisations',
    'description': 'Odoo module for CTL customisations',
    'author': 'Remixcom',
    'depends': [
        'base',
        'project',
        'stock'
    ],
    'data': [
        'data/ir.model.access.csv',
        'views/project.xml',
        'views/warehouse.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}
