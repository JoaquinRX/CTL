{
    'name': 'CTL',
    'version': '1.0',
    'summary': 'Odoo module for CTL customizations',
    'description': 'Odoo module for CTL customizations',
    'author': 'Remixcom',
    'depends': [
        'base',
        'project',
        'stock'
    ],
    'data': [
        'data/ir.model.access.csv',
        'views/project.xml',
        'views/task.xml',
        'views/warehouse.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}
