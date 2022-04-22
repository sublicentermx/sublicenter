{
    'name': 'Theme SublicenterMX',
    'description': 'A description for your theme.',
    'version': '1.0',
    'author': 'Rubén Ely Trujillo Pérez',
    'category': 'Theme/Creative',

    'depends': ['website', 'website_sale'],
    'data': [ 
        'views/template/header.xml',
        'views/template/footer.xml'
    ],
    'assets': {
        'web.assets_frontend': [
            'theme_sublicenter/static/scss/main.scss',
            'theme_sublicenter/static/scss/styles.min.css'
        ]
    }
}