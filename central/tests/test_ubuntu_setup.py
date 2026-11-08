"""Instalación CLI: datos privados, fallos explícitos y protección de datos previos."""
from pathlib import Path
import hashlib
import os
import shutil
import sqlite3
import stat
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run_setup(root, *extra):
    command=[
        'php', str(root/'central/ubuntu/setup.php'),
        '--config='+str(root/'etc/config.php'), '--data-dir='+str(root/'data'),
        '--base-url=https://conta.example.test', '--school=Centro ficticio',
        '--name=Administrador de pruebas', '--email=admin@example.test',
        '--password-stdin',
    ]
    for option in extra:
        prefix=option.split('=',1)[0]+'='
        command=[arg for arg in command if not arg.startswith(prefix)]
        command.append(option)
    return subprocess.run(command, input='ClaveFicticiaSoloPruebas123!\n', text=True, capture_output=True)

def test_setup():
    with tempfile.TemporaryDirectory(prefix='central-ubuntu-') as temp:
        root=Path(temp)
        shutil.copytree(SOURCE,root/'central')
        for option in ('--base-url=http://public.example.test',
                       '--config='+str(root/'central/cpanel/config.php'),
                       '--data-dir='+str(root/'central/cpanel')):
            result=run_setup(root,option)
            assert result.returncode != 0, option
            assert not (root/'data/conta-central.sqlite3').exists()
            assert not (root/'etc/config.php').exists()
        result=run_setup(root)
        assert result.returncode == 0, result.stderr
        config=root/'etc/config.php'; database=root/'data/conta-central.sqlite3'
        for path in (config,database,root/'data/packages'):
            assert stat.S_IMODE(path.stat().st_mode)&0o077 == 0, path
        assert not (root/'central/cpanel/config.php').exists()
        assert 'ClaveFicticia' not in config.read_text()+result.stdout+result.stderr
        with sqlite3.connect(database) as db:
            assert db.execute('SELECT role FROM users').fetchall() == [('admin',)]
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert db.execute("SELECT name FROM sqlite_master WHERE name='grade_history'").fetchone()
        original=(digest(config),digest(database))
        result=run_setup(root)
        assert result.returncode != 0
        assert original==(digest(config),digest(database)), 'Se han modificado datos existentes'
        # No recurrir silenciosamente al config.php público si falta el privado.
        public=root/'central/cpanel'
        (public/'config.php').write_text("<?php return ['db_path'=>'PUBLIC','upload_dir'=>'PUBLIC'];")
        env={**os.environ,'CONTA_CONFIG_FILE':str(root/'missing.php')}
        check=subprocess.run(['php','-r',
            'require $argv[1]; try {cfg(); exit(9);} catch (RuntimeException $e) {echo "fallo explícito";}',
            str(public/'bootstrap.php')],env=env,capture_output=True,text=True)
        assert check.returncode==0 and 'fallo explícito' in check.stdout
        guard=subprocess.run(['php',str(public/'install.php')],env=env,capture_output=True,text=True)
        assert 'Instalación web deshabilitada' in guard.stdout
        assert original==(digest(config),digest(database))
        # Eliminar solo la configuración tampoco permite reinstalar sobre SQLite.
        config.unlink()
        result=run_setup(root)
        assert result.returncode != 0 and not config.exists()
        assert digest(database)==original[1]
    print('OK: instalación CLI, SQLite íntegro, permisos privados, HTTPS, no sobrescritura y cierre del instalador web')

if __name__=='__main__':
    test_setup()
