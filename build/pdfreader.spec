# PyInstaller spec — onefile, windowed.
# Build on each target OS:  uv run pyinstaller build/pdfreader.spec
from PyInstaller.utils.hooks import collect_dynamic_libs

# pypdfium2 ships the native PDFium shared library; make sure it is bundled.
binaries = collect_dynamic_libs("pypdfium2")

a = Analysis(
    ["../src/run_pdfreader.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=[],
    hiddenimports=["pdfreader", "pdfreader.app"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="pdfreader",
    debug=False,
    strip=False,
    upx=True,
    console=False,  # windowed (no terminal)
    onefile=True,
)
