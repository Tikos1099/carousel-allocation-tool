from playwright.sync_api import sync_playwright

html = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;700;900&family=Playfair+Display:wght@700&display=swap');

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    width: 794px;
    height: 1123px;
    font-family: 'Montserrat', sans-serif;
    background: #fff;
    overflow: hidden;
  }

  /* ── HEADER BANDE VERTE ── */
  .header {
    background: linear-gradient(135deg, #1a6b3c 0%, #2e9e5b 60%, #4dc97e 100%);
    height: 260px;
    position: relative;
    display: flex;
    align-items: flex-end;
    padding: 0 50px 30px 50px;
    overflow: hidden;
  }

  .header::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 280px; height: 280px;
    border-radius: 50%;
    background: rgba(255,255,255,0.07);
  }
  .header::after {
    content: '';
    position: absolute;
    bottom: -80px; right: 120px;
    width: 200px; height: 200px;
    border-radius: 50%;
    background: rgba(255,255,255,0.05);
  }

  .badge {
    background: #fff;
    color: #1a6b3c;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding: 6px 14px;
    border-radius: 20px;
    display: inline-block;
    margin-bottom: 14px;
  }

  .header-content { z-index: 2; }

  .header h1 {
    font-family: 'Playfair Display', serif;
    font-size: 42px;
    color: #fff;
    line-height: 1.1;
    font-weight: 700;
  }
  .header h1 span {
    color: #a8f0c6;
  }

  .header .subtitle {
    color: rgba(255,255,255,0.85);
    font-size: 13px;
    font-weight: 400;
    margin-top: 8px;
    letter-spacing: 0.5px;
  }

  /* ── BANDE ÉLECTION ── */
  .election-bar {
    background: #0d3d22;
    color: #fff;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 3px;
    text-transform: uppercase;
    text-align: center;
    padding: 10px;
  }

  /* ── CORPS ── */
  .body {
    padding: 40px 50px 0 50px;
  }

  .intro {
    font-size: 13.5px;
    color: #444;
    line-height: 1.8;
    border-left: 4px solid #2e9e5b;
    padding-left: 18px;
    margin-bottom: 36px;
    font-weight: 300;
  }
  .intro strong { color: #1a6b3c; font-weight: 600; }

  /* ── GRILLE 3 PILIERS ── */
  .pillars {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 18px;
    margin-bottom: 36px;
  }

  .pillar {
    border-radius: 12px;
    padding: 22px 18px;
    position: relative;
    overflow: hidden;
  }
  .pillar-1 { background: linear-gradient(145deg, #e8f8ef, #d0f0e0); }
  .pillar-2 { background: linear-gradient(145deg, #e8f0ff, #d0e0ff); }
  .pillar-3 { background: linear-gradient(145deg, #fff8e8, #ffefd0); }

  .pillar-icon {
    font-size: 28px;
    margin-bottom: 10px;
    display: block;
  }
  .pillar h3 {
    font-size: 13px;
    font-weight: 700;
    color: #1a1a2e;
    margin-bottom: 8px;
  }
  .pillar p {
    font-size: 11px;
    color: #555;
    line-height: 1.6;
    font-weight: 300;
  }

  .pillar-num {
    position: absolute;
    top: 12px; right: 14px;
    font-size: 36px;
    font-weight: 900;
    color: rgba(0,0,0,0.06);
    line-height: 1;
  }

  /* ── CITATION ── */
  .quote-block {
    background: linear-gradient(135deg, #1a6b3c, #2e9e5b);
    border-radius: 12px;
    padding: 26px 30px;
    margin-bottom: 36px;
    display: flex;
    align-items: center;
    gap: 20px;
  }
  .quote-mark {
    font-size: 72px;
    color: rgba(255,255,255,0.25);
    font-family: 'Playfair Display', serif;
    line-height: 0.7;
    flex-shrink: 0;
  }
  .quote-text {
    color: #fff;
    font-size: 14px;
    line-height: 1.7;
    font-style: italic;
    font-weight: 300;
  }
  .quote-author {
    color: #a8f0c6;
    font-size: 11px;
    font-weight: 600;
    margin-top: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
  }

  /* ── STATS ROW ── */
  .stats {
    display: flex;
    gap: 0;
    border: 1.5px solid #e0e0e0;
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 36px;
  }
  .stat {
    flex: 1;
    padding: 20px;
    text-align: center;
    border-right: 1.5px solid #e0e0e0;
  }
  .stat:last-child { border-right: none; }
  .stat .num {
    font-size: 30px;
    font-weight: 900;
    color: #1a6b3c;
    line-height: 1;
  }
  .stat .label {
    font-size: 10px;
    color: #888;
    margin-top: 5px;
    font-weight: 500;
    letter-spacing: 0.5px;
  }

  /* ── FOOTER ── */
  .footer {
    background: #0d3d22;
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 50px;
  }
  .footer-logo {
    color: #fff;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.5px;
  }
  .footer-logo span { color: #4dc97e; }
  .footer-info {
    color: rgba(255,255,255,0.5);
    font-size: 10px;
    letter-spacing: 1px;
  }
  .footer-dot {
    width: 8px; height: 8px;
    background: #4dc97e;
    border-radius: 50%;
  }
</style>
</head>
<body>

  <div class="header">
    <div class="header-content">
      <div class="badge">Municipales 2026</div>
      <h1>Mieux Vivre<br><span>Puteaux</span></h1>
      <p class="subtitle">Pour une ville plus humaine, verte et solidaire</p>
    </div>
  </div>

  <div class="election-bar">Élections Municipales 2026 — Site Officiel</div>

  <div class="body">

    <p class="intro">
      <strong>Mieux Vivre Puteaux</strong> est un mouvement citoyen engagé pour transformer
      notre ville avec des valeurs de <strong>solidarité</strong>, d'<strong>écologie</strong>
      et de <strong>démocratie locale</strong>. Ensemble, construisons le Puteaux de demain.
    </p>

    <div class="pillars">
      <div class="pillar pillar-1">
        <span class="pillar-num">01</span>
        <span class="pillar-icon">🌿</span>
        <h3>Écologie Urbaine</h3>
        <p>Plus d'espaces verts, mobilité douce, réduction des nuisances et ville durable pour tous.</p>
      </div>
      <div class="pillar pillar-2">
        <span class="pillar-num">02</span>
        <span class="pillar-icon">🤝</span>
        <h3>Solidarité & Services</h3>
        <p>Soutien aux familles, accès aux services publics de qualité, aide aux seniors et aux jeunes.</p>
      </div>
      <div class="pillar pillar-3">
        <span class="pillar-num">03</span>
        <span class="pillar-icon">🗳️</span>
        <h3>Démocratie Locale</h3>
        <p>Budget participatif, conseils de quartier, transparence et concertation citoyenne.</p>
      </div>
    </div>

    <div class="quote-block">
      <div class="quote-mark">"</div>
      <div>
        <p class="quote-text">
          Puteaux mérite une municipalité à l'écoute de ses habitants,
          qui agit avec transparence et ambition pour l'avenir de nos quartiers.
        </p>
        <p class="quote-author">— Liste Mieux Vivre Puteaux, 2026</p>
      </div>
    </div>

    <div class="stats">
      <div class="stat">
        <div class="num">47 000</div>
        <div class="label">Habitants</div>
      </div>
      <div class="stat">
        <div class="num">12</div>
        <div class="label">Quartiers</div>
      </div>
      <div class="stat">
        <div class="num">5</div>
        <div class="label">Engagements clés</div>
      </div>
      <div class="stat">
        <div class="num">2026</div>
        <div class="label">Élections</div>
      </div>
    </div>

  </div>

  <div class="footer">
    <div class="footer-logo">Mieux Vivre <span>Puteaux</span></div>
    <div class="footer-dot"></div>
    <div class="footer-info">www.mieuxvivreputeaux.fr — 2026</div>
  </div>

</body>
</html>
"""

output_path = r"C:\Users\ASA\Downloads\mieuxvivreputeaux_test.pdf"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.set_content(html, wait_until="networkidle")
    page.pdf(
        path=output_path,
        width="794px",
        height="1123px",
        print_background=True,
    )
    browser.close()

print(f"PDF généré : {output_path}")
