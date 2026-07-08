/* Shared editorial helpers — loaded after content-data.js */
(function (g) {
  var MON = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];

  g.MDCT = g.MDCT || {};

  g.MDCT.ago = function (iso, now) {
    now = now || new Date();
    var m = Math.round((now - new Date(iso)) / 6e4);
    if (m < 5) return 'just now';
    if (m < 60) return m + 'm ago';
    var h = Math.round(m / 60);
    if (h < 24) return h + 'h ago';
    var d = Math.round(h / 24);
    return d === 1 ? 'Yesterday' : d + 'd ago';
  };

  // Hot window: stories from the last 15 hours are "hot".
  // <=6h -> Breaking (red pill) · <=15h -> Fresh (gold pill) · older -> Latest
  g.MDCT.HOT_HOURS = 15;
  g.MDCT.recency = function (iso, now) {
    now = now || new Date();
    var h = (now - new Date(iso)) / 36e5;
    if (h <= 6) return { label: 'Breaking', cls: 'wire-tag-breaking', hot: true, breaking: true };
    if (h <= g.MDCT.HOT_HOURS) return { label: 'Fresh', cls: 'wire-tag-fresh', hot: true, breaking: false };
    return { label: 'Latest', cls: '', hot: false, breaking: false };
  };

  g.MDCT.dateLabel = function (iso) {
    var d = new Date(iso);
    return MON[d.getMonth()] + ' ' + String(d.getDate()).padStart(2, '0');
  };

  // Category accent colors — used for card rules and tag text.
  g.MDCT.tagColor = function (tag) {
    var T = {
      'Power & Grid': '#E03131', 'Local Government': '#7fb0e0', 'Policy': '#c9a24b',
      'Water': '#5bb3a6', 'Money': '#9bc49b', 'Explainers': '#b07fd0',
    };
    return T[tag] || '#9b9794';
  };

  /* ---- Live feed (Grok agent pipeline) ----------------------------------
     Agents commit `live-data.json` to the repo root:
       { "updated_at": ISO, "stories": [headline objects], "meetings": [...] }
     Pages hot-load it here — no rebuild needed. content-data.js stays the
     curated fallback if the file is missing or invalid.                     */
  g.MDCT.loadLive = function (cb) {
    if (g.MDCT._livePromise) { g.MDCT._livePromise.then(cb, cb); return; }
    var validStory = function (s) {
      return s && typeof s.title === 'string' && s.title.length > 10 &&
        typeof s.url === 'string' && /^https:\/\//.test(s.url) &&
        s.iso && !isNaN(new Date(s.iso)) &&
        typeof s.source === 'string' && s.source &&
        /^(metro|west|mid|north|statewide)$/.test(s.region || '');
    };
    var validMeeting = function (m) {
      return m && m.iso && !isNaN(new Date(m.iso + 'T00:00:00')) &&
        m.body && m.topic && /^https:\/\//.test(m.link || '');
    };
    g.MDCT._livePromise = fetch('live-data.json', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) return;
        var stories = (d.stories || []).filter(validStory);
        var meetings = (d.meetings || []).filter(validMeeting);
        if (stories.length >= 3) g.MDCT_HEADLINES = stories;
        if (meetings.length) {
          meetings.forEach(function (m) { if (m.stream && !/^https:\/\//.test(m.stream)) delete m.stream; });
          // merge with the curated list (agent finds + hand-tracked), dedupe by date+body
          var seen = {};
          meetings.forEach(function (m) { seen[(m.iso + '|' + m.body).toLowerCase()] = true; });
          (g.MDCT_MEETINGS || []).forEach(function (m) {
            var k = (m.iso + '|' + m.body).toLowerCase();
            if (!seen[k]) { seen[k] = true; meetings.push(m); }
          });
          g.MDCT_MEETINGS = meetings;
        }
        if (d.updated_at && !isNaN(new Date(d.updated_at))) g.MDCT_UPDATED = d.updated_at;
      })
      .catch(function () {});
    g.MDCT._livePromise.then(cb, cb);
  };

  /* Submit email (+ optional ZIP) to the Mailchimp audience via a hidden
     form + iframe (the standard embedded-form pattern; no API key needed). */
  g.MDCT.subscribe = function (email, zip) {
    var cfg = g.MDCT_NEWSLETTER || {};
    if (!cfg.form_action || !email || email.indexOf('@') < 1) return false;
    try {
      var doc = document;
      var fr = doc.getElementById('mdct-mc-frame');
      if (!fr) {
        fr = doc.createElement('iframe');
        fr.id = 'mdct-mc-frame'; fr.name = 'mdct-mc-frame';
        fr.style.display = 'none'; fr.setAttribute('aria-hidden', 'true');
        doc.body.appendChild(fr);
      }
      var f = doc.createElement('form');
      f.action = cfg.form_action; f.method = 'POST'; f.target = 'mdct-mc-frame'; f.style.display = 'none';
      var add = function (n, v) { var i = doc.createElement('input'); i.type = 'hidden'; i.name = n; i.value = v; f.appendChild(i); };
      add(cfg.email_tag || 'EMAIL', email.trim());
      if (zip && String(zip).trim()) add(cfg.zip_tag || 'ZIP', String(zip).trim());
      if (cfg.honeypot) add(cfg.honeypot, '');
      doc.body.appendChild(f); f.submit();
      setTimeout(function () { try { f.remove(); } catch (e) {} }, 4000);
      return true;
    } catch (e) { return false; }
  };

  g.MDCT.sourceMeta = function (w) {
    var u = (w.url || '').toLowerCase();
    if (/x\.com|twitter\.com/.test(u)) return { source: 'X', sourceKind: 'src-x' };
    if (/reddit\.com/.test(u)) return { source: 'Reddit', sourceKind: 'src-reddit' };
    return { source: w.source, sourceKind: 'src-news' };
  };

  g.MDCT.headlines = function () {
    return (g.MDCT_HEADLINES || []).slice().sort(function (a, b) {
      return new Date(b.iso) - new Date(a.iso);
    });
  };

  g.MDCT.meetings = function () {
    var now = new Date();
    now.setHours(0, 0, 0, 0);
    return (g.MDCT_MEETINGS || []).filter(function (m) {
      return new Date(m.iso + 'T00:00:00') >= now;
    }).sort(function (a, b) { return a.iso.localeCompare(b.iso); });
  };

  g.MDCT.stats = function () {
    return g.MDCT_STATS || { projects: 0, disclosedGW: '0', pauses: 0, communities: 0, statusBreakdown: [], byRegion: [] };
  };

  g.MDCT.updatedLabel = function () {
    if (!g.MDCT_UPDATED) return '';
    return g.MDCT.ago(g.MDCT_UPDATED);
  };

  g.MDCT.mapPoints = function () {
    if (g.TRACKER_DATA && g.TRACKER_DATA.map_points) return g.TRACKER_DATA.map_points;
    return [];
  };

  g.MDCT.countyRegion = function (county) {
    var west = ['Kent','Kalamazoo','Ottawa','Cass','Mecosta','Muskegon','Allegan','Berrien','Van Buren'];
    var mid = ['Ingham','Saginaw','Genesee','Jackson','Livingston','Shiawassee','Bay','Clinton'];
    var north = ['Marquette','Grand Traverse','Kalkaska','Otsego','Antrim','Chippewa','Delta','Emmet','Mackinac'];
    if (west.indexOf(county) >= 0) return 'west';
    if (mid.indexOf(county) >= 0) return 'mid';
    if (north.indexOf(county) >= 0) return 'north';
    return 'metro';
  };

  g.MDCT.mapStatusKey = function (status, layer) {
    if (layer === 'moratoria') return 'Moratorium';
    var s = (status || '').toLowerCase();
    if (/under construction|construction/.test(s)) return 'Construction';
    if (/operating|approved|conditionally/.test(s)) return 'Operating';
    if (/proposed|review|pending|filed/.test(s)) return 'Proposed';
    if (/withdrawn|rejected|halted|dead/.test(s)) return 'Withdrawn';
    if (/moratorium|pause/.test(s)) return 'Moratorium';
    return 'Proposed';
  };

  g.MDCT.parseMW = function (v) {
    if (!v) return 0;
    return parseFloat(String(v).replace(/,/g, '')) || 0;
  };

  g.MDCT.recordFromPoint = function (p, id) {
    var layer = p.layer || 'projects';
    var type = layer === 'moratoria' ? 'moratorium' : (layer === 'meetings' ? 'meeting' : 'site');
    var statusKey = g.MDCT.mapStatusKey(p.status, layer);
    return {
      id: id,
      type: type,
      name: p.name,
      city: p.municipality || '',
      county: p.county || '',
      region: g.MDCT.countyRegion(p.county || ''),
      operator: p.developer || '—',
      status: statusKey,
      rawStatus: p.status || '',
      load: g.MDCT.parseMW(p.power_mw),
      loadLabel: p.power_mw ? p.power_mw + ' MW' : 'Undisclosed',
      lat: p.latitude,
      lng: p.longitude,
      updated: p.verified_date || '',
      note: p.note || '',
      sourceUrl: p.source_url || '',
      sourceName: p.source_name || '',
      confidence: p.confidence || '',
      mType: p.status || 'Moratorium / pause',
      expires: p.note || '—',
    };
  };
})(typeof window !== 'undefined' ? window : globalThis);