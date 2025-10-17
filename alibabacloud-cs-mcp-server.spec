# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('src/prometheus_metrics_guidance', 'prometheus_metrics_guidance')]
binaries = []
hiddenimports = ['fastmcp', 'fastmcp.server', 'fastmcp.client', 'fastmcp.transport', 'loguru', 'pydantic', 'pydantic.fields', 'pydantic.main', 'alibabacloud_cs20151215', 'alibabacloud_credentials', 'kubernetes', 'kubernetes.client', 'kubernetes.config', 'yaml', 'dotenv', 'aiofiles', 'aiohttp', 'requests', 'ack_audit_log_handler', 'ack_controlplane_log_handler', 'config', 'interfaces.runtime_provider', 'runtime_provider', 'ack_cluster_handler', 'kubectl_handler', 'ack_prometheus_handler', 'ack_diagnose_handler', 'ack_inspect_handler', 'kubeconfig_context_manager', 'models', 'utils.api_error', 'utils.utils']
tmp_ret = collect_all('fastmcp')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pydantic')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('loguru')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('alibabacloud_cs20151215')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('alibabacloud_credentials')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('kubernetes')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['src/main_server.py'],
    pathex=['.', 'src', 'src/interfaces', 'src/utils'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='alibabacloud-ack-mcp-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
