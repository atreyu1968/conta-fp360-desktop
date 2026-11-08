import { useCallback, useEffect, useState } from 'react';
import { ArrowDown, ArrowDownRight, ArrowRight, ArrowUpRight, ChevronRight, Database, Download, HardDrive, Layers3, RefreshCw, WifiOff } from 'lucide-react';

const REPO = 'https://github.com/atreyu1968/conta-fp360-desktop';
const RELEASES = `${REPO}/releases`;
const RELEASE_LIST = 'https://api.github.com/repos/atreyu1968/conta-fp360-desktop/releases?per_page=1';

type Asset = { name: string; browser_download_url: string };
type Release = { name?: string; tag_name: string; html_url: string; assets: Asset[] };
type DownloadStatus = 'loading' | 'available' | 'none' | 'error';
type Platform = 'windows' | 'linux' | 'mac-arm' | 'mac-intel';

const platforms: { key: Platform; label: string }[] = [
  { key: 'windows', label: 'Windows' },
  { key: 'linux', label: 'Linux' },
  { key: 'mac-arm', label: 'macOS · Apple Silicon' },
  { key: 'mac-intel', label: 'macOS · Intel' },
];

function productFor(name: string): 'studio' | 'aula' | null {
  const lower = name.toLowerCase();
  if (lower.includes('studio')) return 'studio';
  if (lower.includes('aula')) return 'aula';
  return null;
}

function platformFor(name: string): Platform | null {
  const lower = name.toLowerCase();
  if (lower.endsWith('.exe')) return 'windows';
  if (lower.endsWith('.appimage')) return 'linux';
  if (lower.endsWith('.app.tar.gz') && lower.includes('darwin-aarch64')) return 'mac-arm';
  if (lower.endsWith('.app.tar.gz') && lower.includes('darwin-x86_64')) return 'mac-intel';
  return null;
}

function App() {
  const [status, setStatus] = useState<DownloadStatus>('loading');
  const [release, setRelease] = useState<Release | null>(null);
  const [attempt, setAttempt] = useState(0);

  const loadRelease = useCallback(async (signal: AbortSignal) => {
    setStatus('loading');
    try {
      const response = await fetch(RELEASE_LIST, {
        signal,
        headers: { Accept: 'application/vnd.github+json' },
      });
      if (!response.ok) throw new Error(`GitHub respondió ${response.status}`);
      const results = (await response.json()) as Release[];
      if (!Array.isArray(results)) throw new Error('Respuesta de publicaciones no válida');
      const result = results[0];
      if (!result) {
        setRelease(null);
        setStatus('none');
        return;
      }
      if (!Array.isArray(result.assets)) throw new Error('Respuesta de publicación no válida');
      const actualBinaries = result.assets.filter((asset) => productFor(asset.name) && platformFor(asset.name));
      if (!actualBinaries.length) {
        setRelease(null);
        setStatus('none');
        return;
      }
      setRelease({ ...result, assets: actualBinaries });
      setStatus('available');
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      setRelease(null);
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadRelease(controller.signal);
    return () => controller.abort();
  }, [loadRelease, attempt]);

  const getAsset = (product: 'studio' | 'aula', platform: Platform) =>
    release?.assets.find((asset) => productFor(asset.name) === product && platformFor(asset.name) === platform);

  return (
    <div className="site-shell">
      <header className="wrap topbar">
        <a className="brand" href="#inicio" aria-label="CONTA FP360, inicio">
          <img src={`${import.meta.env.BASE_URL}conta-fp360-logo.png`} width="37" height="37" alt="Logotipo de CONTA FP360" />
          <span className="brand-name">CONTA FP360<span>APRENDER HACIENDO</span></span>
        </a>
        <nav className="navlinks" aria-label="Navegación principal">
          <a href="#como-funciona">Cómo funciona</a>
          <a href="#central">Central</a>
          <a className="nav-cta" href="#descargas">Descargar gratis <ArrowDownRight size={14} /></a>
        </nav>
      </header>

      <main>
        <section className="wrap hero" id="inicio">
          <div className="eyebrow reveal">Contabilidad para FP · Suite de escritorio</div>
          <h1 className="display reveal reveal-delay">Del ejercicio<br />a la <em>práctica.</em></h1>
          <p className="hero-copy reveal reveal-delay">Una misma suite para enseñar contabilidad con las manos en la masa. El profesorado prepara y publica; el alumnado practica y resuelve. Cada cual, en su aplicación.</p>
          <div className="hero-note"><strong>Gratis</strong> para Windows,<br />Linux y macOS</div>

          <div className="roles">
            <article className="role-card studio">
              <div className="role-top"><span className="role-tag">Para docentes</span><span className="role-index">01 / 02</span></div>
              <div>
                <h2>Studio</h2>
                <p>Crea ejercicios de contabilidad y publícalos para tu clase.</p>
              </div>
              <div className="role-bottom"><a className="role-link" href="#descargas">Explorar Studio <ArrowRight size={15} /></a><span className="role-symbol" aria-hidden="true">S</span></div>
            </article>
            <article className="role-card aula">
              <div className="role-top"><span className="role-tag">Para estudiantes</span><span className="role-index">02 / 02</span></div>
              <div>
                <h2>Aula</h2>
                <p>Practica a tu ritmo y completa los ejercicios de clase.</p>
              </div>
              <div className="role-bottom"><a className="role-link" href="#descargas">Explorar Aula <ArrowRight size={15} /></a><span className="role-symbol" aria-hidden="true">A</span></div>
            </article>
          </div>
          <div className="offline-strip">
            <span><i className="offline-dot" /> Primero en tu equipo</span>
            <span>Sin conexión para trabajar</span>
            <span>Datos locales · SQLite</span>
          </div>
        </section>

        <section className="wrap section" id="como-funciona">
          <div className="split-intro">
            <div>
              <div className="section-kicker">01 — Dos herramientas, un recorrido</div>
              <h2>Un flujo claro.<br />De principio a fin.</h2>
            </div>
            <p className="section-lead">Studio y Aula no son dos nombres para lo mismo. Cada aplicación tiene su papel en el trabajo diario de una clase de Formación Profesional.</p>
          </div>
          <div className="workflow">
            <article className="workflow-panel">
              <span className="num">EN EL PUESTO DOCENTE / STUDIO</span>
              <h3>Diseñar. Publicar.</h3>
              <p>El docente prepara actividades y las pone a disposición de su alumnado.</p>
              <div className="workflow-list"><span>Crear ejercicios</span><span>Organizar contenidos</span><span>Publicar actividades</span></div>
            </article>
            <div className="flow-arrow"><ArrowRight size={26} strokeWidth={1.3} /></div>
            <article className="workflow-panel">
              <span className="num">EN EL PUESTO DEL ALUMNO / AULA</span>
              <h3>Practicar. Resolver.</h3>
              <p>El estudiante abre las actividades disponibles y trabaja los ejercicios en Aula.</p>
              <div className="workflow-list"><span>Practicar contabilidad</span><span>Completar ejercicios</span><span>Trabajar sin conexión</span></div>
            </article>
          </div>
        </section>

        <section className="section offline-section">
          <div className="wrap">
            <div className="offline-content">
              <div className="section-kicker">02 — Hecho para el aula real</div>
              <h2>Tu trabajo vive en tu equipo. <span>La conexión es opcional.</span></h2>
              <p className="section-lead">Studio y Aula son aplicaciones de escritorio con almacenamiento local SQLite. Se puede trabajar sin conexión a internet.</p>
              <div className="offline-points">
                <div className="offline-point"><b><HardDrive size={16} /> Aplicaciones de escritorio</b>Instaladas en Windows, Linux o macOS.</div>
                <div className="offline-point"><b><Database size={16} /> Datos locales</b>La información de trabajo se guarda en SQLite en el equipo.</div>
                <div className="offline-point"><b><WifiOff size={16} /> Modo sin conexión</b>El uso habitual de Studio y Aula no requiere internet.</div>
              </div>
            </div>
          </div>
        </section>

        <section className="wrap section" id="central">
          <div className="central-block">
            <div className="central-visual" aria-label="Representación esquemática de un panel de clases">
              <div className="central-window">
                <div className="window-bar"><i /><i /><i /></div>
                <div className="window-line short" />
                <div className="window-line" />
                <div className="class-row"><span>Grupo · Contabilidad</span><span>CLASE</span></div>
                <div className="class-row"><span>Actividad · Ciclo contable</span><span>ENVIADA</span></div>
                <div className="window-line short" />
              </div>
            </div>
            <div className="central-copy">
              <div className="section-kicker">03 — Cuando la clase comparte</div>
              <h2>Central conecta.<br />Si lo necesitas.</h2>
              <p>Central es un servidor PHP opcional para compartir clases y asignaciones entre Studio y Aula. No es necesario para usar las aplicaciones de escritorio: la suite sigue siendo útil de forma local y sin conexión.</p>
              <span className="optional-badge"><Layers3 size={13} /> Complemento opcional · servidor PHP</span>
            </div>
          </div>
        </section>

        <section className="downloads" id="descargas">
          <div className="wrap">
            <div className="downloads-header">
              <div><div className="section-kicker">04 — Instala y empieza</div><h2>Descargas<br />de escritorio.</h2></div>
              <p className="download-caption">Gratis para Windows, Linux y macOS. Los instaladores aparecen aquí cuando hay una publicación disponible.</p>
            </div>
            <div className="release-state" role="status" aria-live="polite" data-testid="status-release">
              <div>
                <div className="state-label">
                  <i className={`state-icon ${status === 'available' ? 'ready' : status === 'error' ? 'error' : ''}`} />
                  {status === 'loading' && 'Comprobando la última publicación'}
                  {status === 'available' && `Versión disponible · ${release?.name || release?.tag_name}`}
                  {status === 'none' && 'Aún no hay una publicación disponible'}
                  {status === 'error' && 'No se pudieron consultar las descargas'}
                </div>
                <p style={{ marginTop: 8 }}>
                  {status === 'loading' && 'Buscando instaladores publicados en GitHub…'}
                  {status === 'available' && 'Enlaces directos a los archivos publicados en GitHub Releases.'}
                  {status === 'none' && <>No hay instaladores publicados ahora. <a className="release-link" href={RELEASES} target="_blank" rel="noopener noreferrer">Consultar publicaciones en GitHub <ArrowUpRight size={12} /></a></>}
                  {status === 'error' && 'La consulta puede fallar por conexión o disponibilidad del servicio. Inténtalo de nuevo.'}
                </p>
              </div>
              {(status === 'error' || status === 'none') && <button className="retry-button" onClick={() => setAttempt((value) => value + 1)} data-testid="button-retry-release"><RefreshCw size={13} /> Volver a comprobar</button>}
              {status === 'loading' && <div style={{ width: 122 }} className="skeleton" />}
              {status === 'available' && <a href={release?.html_url || RELEASES} className="release-link" target="_blank" rel="noopener noreferrer">Ver publicación <ArrowUpRight size={13} /></a>}
            </div>

            <div className="download-grid">
              {(['studio', 'aula'] as const).map((product) => (
                <article className={`download-card ${product === 'aula' ? 'aula-card' : ''}`} key={product} data-testid={`card-download-${product}`}>
                  <div className="download-card-top"><h3>{product === 'studio' ? 'Studio' : 'Aula'}</h3><span className="code">{product === 'studio' ? 'DOCENTES / 01' : 'ESTUDIANTES / 02'}</span></div>
                  <div className="platforms">
                    {platforms.map((platform) => {
                      const asset = getAsset(product, platform.key);
                      return <div className="platform" key={platform.key} data-testid={`platform-${product}-${platform.key}`}>
                        <b>{platform.label}</b>
                        {status === 'loading' ? <span className="skeleton" style={{ width: 63 }} /> : asset ? (
                          <a href={asset.browser_download_url} target="_blank" rel="noopener noreferrer" data-testid={`download-${product}-${platform.key}`} aria-label={`Descargar ${product === 'studio' ? 'Studio' : 'Aula'} para ${platform.label}`}>
                            <Download size={12} /> Descargar <ArrowUpRight size={11} />
                          </a>
                        ) : <span className="platform-empty">{status === 'available' ? 'No disponible' : status === 'none' ? 'Sin publicar' : status === 'error' ? 'No verificado' : 'Comprobando'}</span>}
                      </div>;
                    })}
                  </div>
                  <p className="download-note">{status === 'available' ? `Solo se muestran archivos publicados para ${product === 'studio' ? 'Studio' : 'Aula'}.` : `${product === 'studio' ? 'Crea y publica ejercicios.' : 'Practica y completa actividades.'} Aplicación de escritorio gratuita.`}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="wrap faq">
          <div className="faq-head">
            <div><div className="section-kicker">05 — En pocas palabras</div><h2>Lo esencial,<br />sin letra pequeña.</h2></div>
            <div>
              <article className="faq-item"><span className="qnum">01</span><div><h3>¿Qué aplicación necesito?</h3><p>Studio está pensado para docentes que crean y publican ejercicios. Aula es para estudiantes que practican y completan esas actividades.</p></div></article>
              <article className="faq-item"><span className="qnum">02</span><div><h3>¿Puedo usarlo sin internet?</h3><p>Sí. Studio y Aula son aplicaciones de escritorio offline-first y guardan los datos localmente en SQLite. Central solo hace falta para compartir clases y asignaciones mediante un servidor PHP.</p></div></article>
              <article className="faq-item"><span className="qnum">03</span><div><h3>¿Cuánto cuesta? ¿Qué sistemas admite?</h3><p>Las aplicaciones se ofrecen gratis para Windows, Linux y macOS. Los enlaces de descarga de cada sistema aparecen cuando esos archivos están publicados.</p></div></article>
            </div>
          </div>
        </section>

        <section className="final-cta">
          <div className="wrap final-cta-inner">
            <h2>La contabilidad se aprende practicando.</h2>
            <a href="#descargas">Ver descargas <ChevronRight size={16} /></a>
          </div>
        </section>
      </main>

      <footer className="wrap footer">
        <div className="footer-top">
          <a className="brand" href="#inicio">
            <img src={`${import.meta.env.BASE_URL}conta-fp360-logo.png`} width="37" height="37" alt="" />
            <span className="brand-name">CONTA FP360<span>STUDIO · AULA · CENTRAL</span></span>
          </a>
          <nav className="footer-links" aria-label="Enlaces del proyecto">
            <a href={REPO} target="_blank" rel="noopener noreferrer">Repositorio <ArrowUpRight size={12} /></a>
            <a href={RELEASES} target="_blank" rel="noopener noreferrer">Publicaciones <ArrowUpRight size={12} /></a>
            <a href="#central">Sobre Central <ArrowDown size={12} /></a>
          </nav>
        </div>
        <div className="footer-bottom"><span>Herramientas de contabilidad para Formación Profesional.</span><span>Studio y Aula · Aplicaciones de escritorio</span></div>
      </footer>
    </div>
  );
}

export default App;
