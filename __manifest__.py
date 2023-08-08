{
    'name': 'CTL',
    'version': '1.0',
    'summary': 'Odoo module for CTL customisations',
    'description': 'Odoo module for CTL customisations',
    'author': 'Remixcom',
    'depends': [
        'base',
        'project'
    ],
    'data': [
        'data/ir.model.access.csv',
        'views/project.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'license': 'OPL-1',
    'application': True,
}
