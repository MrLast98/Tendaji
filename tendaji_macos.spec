# -*- mode: python ; coding: utf-8 -*-

a = Analysis(['src/manager.py'],
             pathex=['.'],
             binaries=[],
             datas=[('templates/*', 'templates'), ('localhost.ecc.crt', '.'), ('localhost.ecc.key', '.'), ('static/*', 'static')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False)

pyz = PYZ(a.pure, a.zipped_data)

app = BUNDLE(pyz,
             a.binaries,
             a.zipfiles,
             a.datas,
             name='Tendaji',
             icon='static/favicon.ico', # Set the path to your icon file for macOS
             bundle_identifier='org.lingam.tendaji'
             )
