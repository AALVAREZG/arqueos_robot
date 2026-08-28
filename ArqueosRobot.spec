# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['run_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('.env.example', '.')],
    hiddenimports=[
        'pika',
        'dotenv',
        'tenacity',
        # `rpaframework` es el nombre del paquete en PyPI; el modulo que se
        # importa es `RPA`. Pedirlo por el nombre de PyPI hacia que cada
        # compilacion imprimiera tres ERROR de import inexistente -junto a
        # robocorp.browser y robocorp.truststore, que no estan instalados-, y
        # una compilacion que siempre da errores ensena a ignorarlos.
        'RPA',
        'RPA.Windows',
        'robocorp',
        'robocorp.windows',
        'tkinter',
        'tkinter.ttk',
        'tkinter.scrolledtext',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'sqlite3',
        # Modulos del proyecto que entran por import directo. Se listan
        # explicitamente igual que en gastos_robot.spec: el analisis estatico
        # los encuentra, pero la lista es la que documenta que existen.
        'document_mode',
        'rabbit_heartbeat',
        'logging_setup',
        'json',
        'threading',
        'logging',
        'datetime',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ArqueosRobot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False for GUI app (no console window)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon='icon.ico' if you have an icon file
)
