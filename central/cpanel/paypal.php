<?php
declare(strict_types=1);

/** Configuración privada del proveedor; los cobros se implementan en paypal-payments.php. */
final class PayPalSettingsError extends RuntimeException {}

function paypal_settings_schema(): void {
    db()->exec(<<<'SQL'
CREATE TABLE IF NOT EXISTS central_paypal_settings(
 id INTEGER PRIMARY KEY CHECK(id=1),
 environment TEXT NOT NULL CHECK(environment IN ('sandbox','live')),
 client_hint TEXT NOT NULL,
 encrypted_payload TEXT NOT NULL,
 revision TEXT NOT NULL,
 verification_status TEXT NOT NULL DEFAULT 'unverified',
 checked_at TEXT,
 updated_at TEXT NOT NULL,
 updated_by INTEGER NOT NULL REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS paypal_config_events(
 id INTEGER PRIMARY KEY,
 actor_id INTEGER NOT NULL REFERENCES users(id),
 action TEXT NOT NULL,
 environment TEXT NOT NULL,
 revision TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
SQL);
}

function paypal_settings_row(): ?array {
    return fetch_one('SELECT * FROM central_paypal_settings WHERE id=1');
}

function paypal_settings_public(?array $row): array {
    if (!$row) return ['configured'=>false,'environment'=>'sandbox','revision'=>'none'];
    $private=paypal_settings_decrypt($row);
    return [
        'configured'=>true, 'environment'=>$row['environment'],
        'client_id_hint'=>$row['client_hint'], 'has_secret'=>true,
        'webhook_configured'=>$private['webhook_id']!=='',
        'merchant_configured'=>$private['merchant_id']!=='',
        'webhook_endpoint'=>rtrim((string)(cfg()['base_url']??''),'/').'/api.php?r=paypal_webhook',
        'revision'=>$row['revision'], 'verification_status'=>$row['verification_status'],
        'checked_at'=>$row['checked_at'], 'updated_at'=>$row['updated_at'],
    ];
}

function paypal_private_key(bool $create): string {
    if (!function_exists('sodium_crypto_secretbox')) {
        throw new PayPalSettingsError('Se requiere la extensión sodium de PHP para proteger las credenciales.');
    }
    $dir=realpath(dirname(cfg()['db_path']));
    $root=realpath($_SERVER['DOCUMENT_ROOT'] ?? __DIR__);
    if (!$dir || !$root || $dir===$root || str_starts_with($dir,$root.'/')) {
        throw new PayPalSettingsError('Los datos de Central deben estar fuera del directorio público antes de guardar credenciales.');
    }
    $path=$dir.'/.paypal-config.key';
    if (is_link($path) || (!$create && !is_file($path))) {
        throw new PayPalSettingsError('Falta la clave privada de PayPal. Restaure su copia antes de modificar las credenciales.');
    }
    $mask=umask(0077);
    try { $handle=@fopen($path,$create?'c+b':'rb'); }
    finally { umask($mask); }
    if (!$handle) throw new PayPalSettingsError('No se puede acceder a la clave privada de PayPal. Revise los permisos.');
    try {
        if (!flock($handle,$create?LOCK_EX:LOCK_SH)) {
            throw new PayPalSettingsError('No se pudo bloquear la clave privada de PayPal.');
        }
        $key=stream_get_contents($handle);
        if ($create && $key==='') {
            $key=random_bytes(SODIUM_CRYPTO_SECRETBOX_KEYBYTES);
            if (fwrite($handle,$key)!==strlen($key) || !fflush($handle)) {
                throw new PayPalSettingsError('No se pudo guardar la clave privada de PayPal.');
            }
        }
        if (strlen((string)$key)!==SODIUM_CRYPTO_SECRETBOX_KEYBYTES) {
            throw new PayPalSettingsError('La clave privada de PayPal no es válida. Restaure una copia correcta.');
        }
        if (!@chmod($path,0600)) {
            throw new PayPalSettingsError('No se pudieron proteger los permisos de la clave privada de PayPal.');
        }
        return $key;
    } finally { fclose($handle); }
}

function paypal_settings_decrypt(array $row): array {
    $key=paypal_private_key(false);
    $bytes=base64_decode($row['encrypted_payload'],true);
    $size=SODIUM_CRYPTO_SECRETBOX_NONCEBYTES;
    $plain=is_string($bytes) && strlen($bytes)>$size
        ? sodium_crypto_secretbox_open(substr($bytes,$size),substr($bytes,0,$size),$key) : false;
    if ($plain===false) throw new PayPalSettingsError('No se pudieron descifrar las credenciales. Restaure la clave privada correspondiente.');
    $data=json_decode($plain,true);
    if (!is_array($data) || !isset($data['client_id'],$data['client_secret'])) {
        throw new PayPalSettingsError('La configuración privada de PayPal no es válida.');
    }
    $data['webhook_id']=(string)($data['webhook_id']??'');
    $data['merchant_id']=(string)($data['merchant_id']??'');
    return $data;
}

function paypal_revision(array $in,?array $row): void {
    if (!isset($in['expected_revision']) || !is_string($in['expected_revision']) ||
        !hash_equals($row['revision']??'none',$in['expected_revision'])) {
        fail(409,'La configuración ha cambiado. Actualice el formulario antes de continuar.');
    }
}

function paypal_config_event(array $user,string $action,string $environment,string $revision): void {
    db()->prepare('INSERT INTO paypal_config_events(actor_id,action,environment,revision) VALUES(?,?,?,?)')
        ->execute([$user['id'],$action,$environment,$revision]);
}

/** Clasifica sin devolver ni registrar el token OAuth o la respuesta del proveedor. */
function paypal_oauth_result(int $code,string $body,bool $transportOk): string {
    if (!$transportOk) return 'unavailable';
    if (in_array($code,[401,403],true)) return 'rejected';
    $out=json_decode($body,true);
    return $code===200 && is_array($out) && is_string($out['access_token']??null) &&
        $out['access_token']!=='' && strtolower((string)($out['token_type']??''))==='bearer' &&
        is_numeric($out['expires_in']??null) && (float)$out['expires_in']>0
        ? 'verified' : 'unavailable';
}

function paypal_check_connection(array $row): string {
    if (!function_exists('curl_init')) throw new PayPalSettingsError('Se requiere la extensión curl de PHP para comprobar PayPal.');
    $credentials=paypal_settings_decrypt($row);
    // Lista cerrada: no se admiten URLs del navegador, redirecciones ni servidores alternativos.
    $base=$row['environment']==='live'?'https://api-m.paypal.com':'https://api-m.sandbox.paypal.com';
    $curl=curl_init($base.'/v1/oauth2/token');
    $body='';
    curl_setopt_array($curl,[
        CURLOPT_POST=>true, CURLOPT_POSTFIELDS=>'grant_type=client_credentials',
        CURLOPT_HTTPHEADER=>['Accept: application/json','Content-Type: application/x-www-form-urlencoded'],
        CURLOPT_HTTPAUTH=>CURLAUTH_BASIC,
        CURLOPT_USERPWD=>$credentials['client_id'].':'.$credentials['client_secret'],
        CURLOPT_FOLLOWLOCATION=>false, CURLOPT_PROTOCOLS=>CURLPROTO_HTTPS,
        CURLOPT_SSL_VERIFYPEER=>true, CURLOPT_SSL_VERIFYHOST=>2,
        CURLOPT_CONNECTTIMEOUT=>5, CURLOPT_TIMEOUT=>12,
        CURLOPT_WRITEFUNCTION=>static function($handle,string $chunk) use (&$body): int {
            if (strlen($body)+strlen($chunk)>131072) return 0;
            $body.=$chunk;
            return strlen($chunk);
        },
    ]);
    $ok=curl_exec($curl)!==false;
    $code=(int)curl_getinfo($curl,CURLINFO_RESPONSE_CODE);
    curl_close($curl);
    return paypal_oauth_result($code,$body,$ok);
}

function handle_paypal_settings_route(string $route,string $method,array $user): void {
    if (!in_array($route,['paypal_settings','paypal_test','paypal_delete'],true)) return;
    $owner=strtolower(trim((string)(cfg()['platform_owner_email']??'')));
    if ($user['role']!=='admin' || $owner==='' || !hash_equals($owner,strtolower((string)$user['email']))) {
        fail(403,'La configuración de PayPal está reservada al administrador general.');
    }
    if (($route!=='paypal_settings' && $method!=='POST') ||
        ($route==='paypal_settings' && !in_array($method,['GET','POST'],true))) fail(405,'Método no permitido');
    paypal_settings_schema();
    $row=paypal_settings_row();
    if ($method==='GET') respond(['ok'=>true,'settings'=>paypal_settings_public($row)]);
    $in=json_in();
    paypal_revision($in,$row);
    try {
        if ($route==='paypal_settings') {
            $env=$in['environment']??null;
            if (!in_array($env,['sandbox','live'],true)) fail(422,'Entorno de PayPal incorrecto.');
            if ($env==='live' && ($in['confirm_live']??false)!==true) fail(422,'Confirme expresamente el entorno de producción.');
            $id=$in['client_id']??''; $secret=$in['client_secret']??'';
            $webhookId=$in['webhook_id']??''; $merchantId=$in['merchant_id']??'';
            if (!is_string($id) || !is_string($secret) || !is_string($webhookId) || !is_string($merchantId)) {
                fail(422,'Credenciales de PayPal incorrectas.');
            }
            $id=trim($id); $secret=trim($secret);
            $webhookId=trim($webhookId); $merchantId=trim($merchantId);
            $changedEnv=$row && $env!==$row['environment'];
            if ($changedEnv && ($id==='' || $secret==='')) fail(422,'Al cambiar de entorno debe introducir ambas credenciales del nuevo entorno.');
            $old=$row?paypal_settings_decrypt($row):null;
            if ($old && $id!=='' && $id!==$old['client_id'] && $secret==='') fail(422,'Un Client ID diferente requiere su Client Secret.');
            $id=$id!==''?$id:($old['client_id']??'');
            $secret=$secret!==''?$secret:($old['client_secret']??'');
            $webhookId=$webhookId!==''?$webhookId:($old['webhook_id']??'');
            $merchantId=$merchantId!==''?$merchantId:($old['merchant_id']??'');
            if (!preg_match('/^[A-Za-z0-9_-]{10,512}$/D',$id) || !preg_match('/^[\x21-\x7E]{10,512}$/D',$secret)) {
                fail(422,'Introduzca un Client ID y un Client Secret válidos.');
            }
            if (($webhookId!=='' && !preg_match('/^[A-Za-z0-9_-]{8,256}$/D',$webhookId)) ||
                ($merchantId!=='' && !preg_match('/^[A-Za-z0-9_-]{8,64}$/D',$merchantId))) {
                fail(422,'El ID de webhook o de comercio no tiene un formato válido.');
            }
            $key=paypal_private_key($row===null);
            $nonce=random_bytes(SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);
            $encrypted=base64_encode($nonce.sodium_crypto_secretbox(json_encode(
                ['client_id'=>$id,'client_secret'=>$secret,'webhook_id'=>$webhookId,'merchant_id'=>$merchantId],
                JSON_THROW_ON_ERROR),$nonce,$key));
            $revision=bin2hex(random_bytes(16));
            $values=[$env,'••••'.substr($id,-6),$encrypted,$revision,gmdate('Y-m-d\TH:i:s\Z'),$user['id']];
            $db=db(); $db->beginTransaction();
            if ($row) {
                $sql="UPDATE central_paypal_settings SET environment=?,client_hint=?,encrypted_payload=?,revision=?,updated_at=?,updated_by=?,verification_status='unverified',checked_at=NULL WHERE id=1 AND revision=?";
                $values[]=$row['revision'];
            } else {
                $sql='INSERT INTO central_paypal_settings(environment,client_hint,encrypted_payload,revision,updated_at,updated_by,id) VALUES(?,?,?,?,?,?,1) ON CONFLICT(id) DO NOTHING';
            }
            $stmt=$db->prepare($sql); $stmt->execute($values);
            if ($stmt->rowCount()!==1) { $db->rollBack(); fail(409,'Otra sesión ha cambiado la configuración. Actualice el formulario.'); }
            paypal_config_event($user,'saved',$env,$revision);
            $db->commit();
            respond(['ok'=>true,'settings'=>paypal_settings_public(paypal_settings_row())]);
        }
        if (!$row) fail(422,'Primero debe guardar la configuración de PayPal.');
        if ($route==='paypal_delete') {
            if (($in['confirm_delete']??false)!==true) fail(422,'Confirme la eliminación de las credenciales.');
            $db=db(); $db->beginTransaction();
            $stmt=$db->prepare('DELETE FROM central_paypal_settings WHERE id=1 AND revision=?');
            $stmt->execute([$row['revision']]);
            if ($stmt->rowCount()!==1) { $db->rollBack(); fail(409,'Otra sesión ha cambiado la configuración. Actualice el formulario.'); }
            paypal_config_event($user,'deleted',$row['environment'],$row['revision']);
            $db->commit();
            respond(['ok'=>true,'settings'=>paypal_settings_public(null)]);
        }
        $result=paypal_check_connection($row);
        $db=db(); $db->beginTransaction();
        $stmt=$db->prepare('UPDATE central_paypal_settings SET verification_status=?,checked_at=? WHERE id=1 AND revision=?');
        $stmt->execute([$result,gmdate('Y-m-d\TH:i:s\Z'),$row['revision']]);
        if ($stmt->rowCount()!==1) { $db->rollBack(); fail(409,'La configuración cambió durante la comprobación. Vuelva a comprobarla.'); }
        paypal_config_event($user,$result,$row['environment'],$row['revision']);
        $db->commit();
        $messages=[
            'verified'=>'Credenciales aceptadas por PayPal. No se ha realizado ningún cobro.',
            'rejected'=>'PayPal no ha aceptado estas credenciales en el entorno seleccionado.',
            'unavailable'=>'No se ha podido validar la conexión con PayPal. Revise el entorno y vuelva a intentarlo.',
        ];
        respond(['ok'=>true,'settings'=>paypal_settings_public(paypal_settings_row()),
            'connected'=>$result==='verified','message'=>$messages[$result]]);
    } catch (PayPalSettingsError $error) {
        if (db()->inTransaction()) db()->rollBack();
        fail(503,$error->getMessage());
    }
}
