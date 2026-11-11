/* Trendee Milestone A: read-only Home Assistant sidebar panel.
 * Uses the Home Assistant-provided hass object; no worker credentials in browser.
 */
class TrendeePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this._hass = null;
    this._playlistData = null;
    this._playlistVersion = null;
    this._playlistPending = false;
    this._previewPending = false;
    this._previewFeedback = "";
  }
  set hass(value) {
    this._hass = value;
    this.render();
    this._loadPlaylist();

  }
  connectedCallback() { this.render(); this._loadPlaylist(); }
  async _loadPlaylist() {
    const state = this._hass?.states?.["sensor.trendee_playlist_tracks"];
    if (!state || state.attributes?.ready !== true || !this._hass?.callWS) return;
    const version = state.last_updated;
    if (this._playlistPending || this._playlistVersion === version) return;
    this._playlistPending = true;
    try {
      const data = await this._hass.callWS({type: "trendee/playlist"});
      if (data?.source !== "live_tidal_read_only" ||
          data?.playlist_id !== state.attributes.playlist_id ||
          !Array.isArray(data?.tracks)) throw new Error("Invalid playlist snapshot");
      this._playlistData = data;
      this._playlistVersion = version;
    } catch (err) {
      this._playlistData = null;
      this._playlistVersion = version;
    } finally {
      this._playlistPending = false;
      this.render();
    }
  }
  async _runPreview() {
    const status = this._hass?.states?.["sensor.trend_playlist_preview"];
    if (this._previewPending || status?.attributes?.running === true) return;
    const button = Object.entries(this._hass?.states || {}).find(([id, entity]) =>
      id.startsWith("button.") && entity.attributes?.friendly_name === "Trend Playlist run preview");
    if (!button || !this._hass?.callService) {
      this._previewFeedback = "Preview button unavailable.";
      this.render();
      return;
    }
    this._previewPending = true;
    this._previewFeedback = "Starting preview…";
    this.render();
    try {
      await this._hass.callService("button", "press", {entity_id: button[0]});
      this._previewFeedback = "Preview requested. Wait for the updated review.";
    } catch (_) {
      this._previewFeedback = "Unable to start preview. Check Home Assistant logs.";
    } finally {
      this._previewPending = false;
      this.render();
    }
  }
  _openSidebar() {
    this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
  }
  render() {
    const state = this._hass?.states?.["sensor.trend_playlist_preview"];
    const a = state?.attributes || {};
    const playlist = this._hass?.states?.["sensor.trendee_playlist_tracks"];
    const pa = playlist?.attributes || {};
    const tracks = pa.ready === true && Array.isArray(this._playlistData?.tracks) ? this._playlistData.tracks : [];
    const esc = (v) => String(v ?? "Unavailable").replace(/[&<>"']/g, c => ({
      "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
    }[c]));
    const published = a.published_at ? new Date(a.published_at).toLocaleString() : "Not yet published";
    const busy = a.running === true;
    const review = a.review || {};
    const ready = review.ready === true && !busy;
    const additions = ready && Array.isArray(review.revised_additions) ? review.revised_additions : [];
    const removals = ready && Array.isArray(review.revised_removals) ? review.revised_removals : [];
    const previewButton = Object.entries(this._hass?.states || {}).find(([id, entity]) =>
      id.startsWith("button.") && entity.attributes?.friendly_name === "Trend Playlist run preview");
    const item = (t) => "<li><strong>" + esc(t.title || "Unknown title") + "</strong> · " + esc(t.artist || "Unknown artist") + "</li>";
    const previousSearch = this.shadowRoot.querySelector(".search")?.value || "";
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
        .track { display:flex; align-items:center; gap:12px; padding:12px 0; border-bottom:1px solid var(--divider-color); }
        .track:last-child { border-bottom:0; }
        .track[hidden] { display:none; }
        .cover { width:48px; height:48px; border-radius:6px; object-fit:cover; flex-shrink:0; background:var(--secondary-background-color); }
        .track-text { min-width:0; flex:1; overflow-wrap:anywhere; }
        .track-sub { color:var(--secondary-text-color); font-size:.85rem; margin-top:3px; }
        .track-number { color:var(--secondary-text-color); width:24px; flex-shrink:0; }
        .search { width:100%; box-sizing:border-box; padding:12px; margin:12px 0; border-radius:8px; border:1px solid var(--divider-color); background:var(--card-background-color); color:var(--primary-text-color); font:inherit; }
        a { color:var(--primary-color); }
        .action { padding:11px 16px; border:0; border-radius:8px; background:var(--primary-color); color:white; cursor:pointer; font:inherit; }
        .action:disabled { opacity:.5; cursor:not-allowed; }
        .changes { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:16px; }
        .changes ul { padding-left:20px; line-height:1.7; }
        .warning { border-left:3px solid var(--warning-color, orange); padding-left:12px; }

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
        <section class="card" style="margin-top:16px">
          <h2>Preview &amp; review</h2>
          <p>Calculate proposed changes without updating TIDAL.</p>
          <button type="button" class="action preview" ${busy || this._previewPending || !previewButton ? "disabled" : ""}>Run preview</button>
          <p role="status">${esc(this._previewFeedback || (busy ? "Preview running…" : "Last preview: " + (a.preview_result_at ? new Date(a.preview_result_at).toLocaleString() : "Not run")))}</p>
          ${!previewButton ? "<p>Preview button entity not found.</p>" : ""}
          ${ready ? `
            <p><strong>${esc(review.playlist_name || "Down with the Kids")}</strong> · ${esc(review.unchanged ?? "?")} unchanged · ${esc(review.revised_count ?? "?")} proposed tracks</p>
            <div class="changes">
              <div><h3>Additions (${additions.length})</h3>${additions.length ? "<ul>" + additions.map(item).join("") + "</ul>" : "<p>None</p>"}</div>
              <div><h3>Removals (${removals.length})</h3>${removals.length ? "<ul>" + removals.map(item).join("") + "</ul>" : "<p>None</p>"}</div>
            </div>
            <p>Approval: ${review.approval_recorded ? "recorded" : "not recorded"} · Publish safety check: ${review.publish_preflight_passed ? "passed" : "not passed"}</p>
          ` : `<p>${esc(busy ? "A preview is running. Wait for the new results." : review.reason || "No review available. Run a preview.")}</p>`}
          <p class="warning">Review only. Approval and publishing are not available on this page.</p>
        </section>
        <section class="card" style="margin-top:16px">
          <h2>Down with the Kids · Playlist</h2>
          <p>${pa.ready === true && this._playlistData ? `${tracks.length} tracks · Live TIDAL snapshot (refreshes every 10 minutes)` : "Live playlist not available yet. The worker may need updating."}</p>
          ${pa.ready === true && this._playlistData ? `<input class="search" type="search" placeholder="Search tracks or artists" aria-label="Search playlist" /><div class="tracks">${tracks.map(t => `<div class="track" data-search="${esc(`${t.title || ""} ${t.artist || ""} ${t.album || ""}`.toLowerCase())}"><span class="track-number">${esc(t.position)}</span>${t.artwork_url && /^https:\/\//.test(t.artwork_url) ? `<img class="cover" loading="lazy" src="${esc(t.artwork_url)}" alt="" />` : `<span class="cover"></span>`}<div class="track-text"><strong>${esc(t.title)}</strong><div class="track-sub">${esc(t.artist)} · ${esc(t.album)}</div></div><a href="https://tidal.com/browse/track/${encodeURIComponent(String(t.tidal_id ?? ""))}" target="_blank" rel="noopener noreferrer" aria-label="Open ${esc(t.title)} in TIDAL">TIDAL</a></div>`).join("")}</div>` : ""}
        </section>
        <p class="note">Preview is a dry run. No action on this page can publish to TIDAL.</p>
      </main>`;
    this.shadowRoot.querySelector(".menu").addEventListener("click", () => this._openSidebar());
    this.shadowRoot.querySelector(".preview").addEventListener("click", () => this._runPreview());
    const search = this.shadowRoot.querySelector(".search");
    if (search) {
      search.value = previousSearch;
      search.addEventListener("input", () => {
      const query = search.value.trim().toLowerCase();
      this.shadowRoot.querySelectorAll(".track").forEach(row => {
        row.hidden = !row.dataset.search.includes(query);
      });
      });
      search.dispatchEvent(new Event("input"));
    }
  }
}
if (!customElements.get("trendee-panel")) customElements.define("trendee-panel", TrendeePanel);
