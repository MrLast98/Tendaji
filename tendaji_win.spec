# -*- mode: python ; coding: utf-8 -*-

a = Analysis(['src/manager.py'],
             pathex=['.'],
             binaries=[],
             datas=[('templates/*', 'templates'), ('localhost.ecc.crt', '.'), ('localhost.ecc.key', '.'), ('static/*', '.')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='Tendaji',
          debug=False,
          console=True,
          icon='static/favicon.ico'
          )

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='Tendaji'
               )
