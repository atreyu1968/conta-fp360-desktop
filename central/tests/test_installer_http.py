#!/usr/bin/env python3
"""Test HTTP del instalador sin config.php y reparación de ruta inválida.

Se ejecuta exclusivamente en PHP integrado con datos ficticios y HOME temporal.
No utiliza el hosting real ni las credenciales del usuario.
"""
from __future__ import annotations
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]/'cpanel'
def request(url: str, form=None):
    data=None if form is None else urllib.parse.urlencode(form).encode('utf-8')
    try:
        with urllib.request.urlopen(urllib.request.Request(url,data=data),timeout=12) as res:
            return res.status,res.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code,e.read().decode('utf-8')
def check(cond, msg):
    if not cond: raise AssertionError(msg)
def run_case(repair: bool):
    with tempfile.TemporaryDirectory(prefix='cfp360-installer-') as temporary:
        root=Path(temporary)
        home=root/'home'; home.mkdir()
        web=root/'web'; shutil.copytree(SOURCE,web)
        if repair:
            (web/'config.php').write_text(
                "<?php return ['install_secret'=>'REEMPLAZAR','base_url'=>'https://mal-configurado.invalid',"
                "'db_path'=>'/sys/central-no-creable.sqlite3','upload_dir'=>'/sys/no-creable',"
                "'require_curriculum_catalog'=>true];\n",encoding='utf-8')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        env={**os.environ,'HOME':str(home)}
        proc=subprocess.Popen(['php','-S',f'127.0.0.1:{port}','-t',str(web)],
                              env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            for attempt in range(60):
                try:
                    status,body=request(base+'/install.php')
                    break
                except (urllib.error.URLError,ConnectionRefusedError):
                    time.sleep(.1)
            else: raise AssertionError('El servidor PHP no ha arrancado')
            check(status==200,'El instalador debe abrir el formulario')
            check('Instalar Central' in body,'El asistente no muestra sus controles')
            check('name="secret"' not in body,'No debe existir un campo de clave de instalación')
            check('Privacidad de directorios' in body,'Debe advertir del acceso público inicial')
            check('PDO con controlador SQLite' in body,'No realiza comprobaciones de requisitos')
            key_file=home/'.conta-fp360'/'instalacion.clave'
            check(not key_file.exists(),'El instalador no debe generar claves de autorización')
            check(not (web/'config.php').exists() or repair,'Antes de enviar el formulario no debe haber configuración creada en el caso nuevo')
            form={'school':'Centro piloto de pruebas','name':'Admin del centro',
                  'email':'admin@example.test','password':'TestPass123456!'}
            status,body=request(base+'/install.php',form)
            check(status==200, 'La instalación debe responder correctamente')
            check('Servidor instalado correctamente' in body,'No se muestra confirmación de instalación')
            check((web/'config.php').is_file(),'No se ha creado config.php')
            config=(web/'config.php').read_text(encoding='utf-8')
            check(str(home/'.conta-fp360') in config,'No se ha guardado la ruta privada correcta')
            check("admin@example.test" in config,'No se ha asignado correctamente el propietario')
            check((home/'.conta-fp360'/'conta-central.sqlite3').is_file(),'No se ha creado SQLite')
            check(not key_file.exists(),'No puede quedar una clave de instalación')
            if repair:
                backups=list((home/'.conta-fp360').glob('config-previa-*.bak'))
                check(backups,'La configuración antigua se debe respaldar en privado')
            status,body=request(base+'/api.php?r=health')
            check(status==200 and '"initialized":true' in body,'Health no confirma inicialización')
            import json
            data=json.dumps({'email':'admin@example.test','password':'TestPass123456!'}).encode()
            req=urllib.request.Request(base+'/api.php?r=login',data=data,headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=12) as resp:
                check(resp.status==200 and b'"token"' in resp.read(),'El administrador no puede iniciar sesión')
            # El instalador se elimina automáticamente si los permisos lo permiten.
            check(not (web/'install.php').exists(),'El instalador ha quedado expuesto después de instalar')
            check(request(base+'/install.php',form)[0]==404,'No puede reinstalar una vez completado')
            print('OK:', 'reparación de config.php' if repair else 'config.php creado automáticamente')
        finally:
            proc.terminate()
            try: proc.communicate(timeout=5)
            except subprocess.TimeoutExpired: proc.kill();proc.communicate()
if __name__=='__main__':
    run_case(False)
    run_case(True)
    print('INSTALADOR CPANEL: 2 PRUEBAS HTTP COMPLETAS CORRECTAS')
