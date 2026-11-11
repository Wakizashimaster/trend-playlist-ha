/* Trendee Milestone A: read-only Home Assistant sidebar panel.
 * Uses the Home Assistant-provided hass object; no worker credentials in browser.
 */
class TrendeePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this._hass = null;
  }
  set hass(value) {
    this._hass = value;
    this.render();
  }
  connectedCallback() { this.render(); }
  _openSidebar() {
    this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
  }
  render() {
    const state = this._hass?.states?.["sensor.trend_playlist_preview"];
    const a = state?.attributes || {};
    const esc = (v) => String(v ?? "Unavailable").replace(/[&<>"']/g, c => ({
      "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
    }[c]));
    const published = a.published_at ? new Date(a.published_at).toLocaleString() : "Not yet published";
    const busy = a.running === true;
    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; color:var(--primary-text-color); background:var(--primary-background-color); min-height:100%; }
        main { max-width:1000px; margin:0 auto; padding:clamp(16px,4vw,36px); }
        header { display:flex; align-items:center; gap:12px; margin-bottom:18px; }
        h1 { font-size:1.8rem; margin:0; }
        .menu { display:none; color:var(--primary-text-color); background:none; border:0; border-radius:8px; padding:10px; font-size:1.25rem; cursor:pointer; }
        .menu:focus-visible { outline:2px solid var(--primary-color); }
        @media (max-width: 870px) { .menu { display:inline-flex; } }
        p { color:var(--secondary-text-color); }
        .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-top:24px; }
        .card { background:var(--card-background-color); border:1px solid var(--divider-color); border-radius:14px; padding:20px; }
        .label { color:var(--secondary-text-color); font-size:.85rem; margin-bottom:10px; }
        .value { font-size:1.2rem; font-weight:600; overflow-wrap:anywhere; }
        .note { font-size:.9rem; margin-top:24px; }
      </style>
      <main>
        <header><button type="button" class="menu" aria-label="Open Home Assistant menu">☰</button><h1>Trendee</h1></header>
        <p>Down with the Kids · Home Assistant control centre</p>
        <div class="grid">
          <section class="card"><div class="label">Worker</div><div class="value">${esc(!state ? "Unavailable" : busy ? "Busy" : "Idle")}</div></section>
          <section class="card"><div class="label">Latest preview</div><div class="value">${esc(a.preview_result ?? "Not run")}</div></section>
          <section class="card"><div class="label">Publish status</div><div class="value">${esc(a.publish_status ?? "Not published")}</div></section>
          <section class="card"><div class="label">Last verified publish</div><div class="value">${esc(published)}</div></section>
        </div>
        <section class="card" style="margin-top:16px">
          <div class="label">Publish details</div>
          <div style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(a.publish_message ?? "No publish details available")}</div>
        </section>
        <p class="note">Milestone A preview: read-only status. Playlist browsing, controls and exclusions arrive in later milestones. No action on this page can change TIDAL.</p>
      </main>`;
    this.shadowRoot.querySelector(".menu").addEventListener("click", () => this._openSidebar());
  }
}
if (!customElements.get("trendee-panel")) customElements.define("trendee-panel", TrendeePanel);
