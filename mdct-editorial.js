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
        /^(se|metro|west|capital|mid|north|statewide)$/.test(s.region || ''); // 'capital' accepted as legacy → normalized to 'mid'
    };
    // Legacy → new region keys, so old data + old agent output keep working.
    var normalizeRegion = function (s) {
      if (s.region === 'metro') s.region = 'se';
      if (s.region === 'capital') s.region = 'mid'; // Capital Region folded into Mid-Michigan
      // if a county is present, region is always derived from it (single source of truth)
      if (s.county) s.region = g.MDCT.countyRegion(s.county);
      return s;
    };
    var validMeeting = function (m) {
      return m && m.iso && !isNaN(new Date(m.iso + 'T00:00:00')) &&
        m.body && m.topic && /^https:\/\//.test(m.link || '');
    };
    g.MDCT._livePromise = fetch('live-data.json', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) return;
        var stories = (d.stories || []).filter(validStory).map(normalizeRegion);
        var meetings = (d.meetings || []).filter(validMeeting);
        if (stories.length >= 3) g.MDCT_HEADLINES = stories;
        if (meetings.length) {
          meetings.forEach(function (m) { if (m.stream && !/^https:\/\//.test(m.stream)) delete m.stream; });
          // Dedupe by date + TOWN (not exact body) so "Saline Township Board of
          // Trustees" and "Saline Township Board" on the same night collapse to one.
          var townKey = function (m) {
            var t = (m.body || '').toLowerCase()
              .replace(/board of trustees|board|planning commission|city council|advisory group|commission|committee|meeting|hearing|—.*$/g, '')
              .replace(/[^a-z ]/g, '').trim().split(/\s+/).slice(0, 2).join(' ');
            return m.iso + '|' + t;
          };
          var seen = {}, merged = [];
          meetings.concat(g.MDCT_MEETINGS || []).forEach(function (m) {
            var k = townKey(m);
            if (!seen[k]) { seen[k] = true; merged.push(m); }
          });
          g.MDCT_MEETINGS = merged;
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
    var isVideo = /youtube\.com|youtu\.be|fb\.watch|facebook\.com\/(watch|reel|share\/v|[^\/]+\/videos)|\/videos?\//.test(u);
    var meta;
    if (/x\.com|twitter\.com/.test(u)) meta = { source: 'X', sourceKind: 'src-x' };
    else if (/reddit\.com/.test(u)) meta = { source: 'Reddit', sourceKind: 'src-reddit' };
    else if (/facebook\.com|fb\.watch/.test(u)) meta = { source: (w.source && !/facebook/i.test(w.source)) ? w.source + ' · via Facebook' : 'Facebook', sourceKind: 'src-news' };
    else if (/youtube\.com|youtu\.be/.test(u)) meta = { source: (w.source && !/youtube/i.test(w.source)) ? w.source + ' · via YouTube' : 'YouTube', sourceKind: 'src-news' };
    else meta = { source: w.source, sourceKind: 'src-news' };
    meta.isVideo = isVideo;
    return meta;
  };

  // Homepage rule (News Director): a story never leaves until a fresh one
  // replaces it — show newest MAX_STORIES, fresh pushes old off the bottom.
  // TOP STORY = biggest fresh story: highest newsworthiness score among the
  // last LEAD_HOURS leads (ties break by newest); the rest stay newest-first.
  g.MDCT.MAX_STORIES = 11;
  g.MDCT.LEAD_HOURS = 12;
  g.MDCT.headlines = function () {
    var all = (g.MDCT_HEADLINES || []).slice().sort(function (a, b) {
      return new Date(b.iso) - new Date(a.iso);
    }).slice(0, g.MDCT.MAX_STORIES);
    var now = Date.now();
    var score = function (s) { return typeof s.judge_score === 'number' ? s.judge_score : 5; };
    var fresh = all.filter(function (s) {
      return (now - new Date(s.iso).getTime()) / 36e5 <= g.MDCT.LEAD_HOURS;
    });
    if (!fresh.length) return all;
    var lead = fresh.slice().sort(function (a, b) {
      return score(b) - score(a) || (new Date(b.iso) - new Date(a.iso));
    })[0];
    return [lead].concat(all.filter(function (s) { return s !== lead; }));
  };

  // Actual start datetime of a meeting from its date + "7:00 PM" time.
  // No time -> end of that day (so an all-day/undated item stays till midnight).
  g.MDCT.meetingStart = function (m) {
    var d = new Date(m.iso + 'T00:00:00');
    var t = String(m.time || '').match(/(\d{1,2}):(\d{2})\s*(a|p)?/i);
    if (t) {
      var h = (+t[1]) % 12;
      if (t[3] && /p/i.test(t[3])) h += 12;
      d.setHours(h, +t[2], 0, 0);
    } else {
      d.setHours(23, 59, 0, 0);
    }
    return d;
  };
  g.MDCT.meetings = function () {
    // A meeting is "upcoming" until ~2h after it starts (still relevant while in
    // session); once it's genuinely past it drops off — no more stale "TONIGHT".
    var cutoff = Date.now() - 2 * 36e5;
    return (g.MDCT_MEETINGS || []).filter(function (m) {
      return g.MDCT.meetingStart(m).getTime() >= cutoff;
    }).sort(function (a, b) { return g.MDCT.meetingStart(a) - g.MDCT.meetingStart(b); });
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

  // Canonical Michigan region map (News Director's taxonomy). Every county maps
  // to exactly one region; region is always DERIVED from county so the two tags
  // never disagree. Regions: se · west · mid · north. (Mid-Michigan spans the
  // Lansing/Jackson/Flint/Saginaw/Bay City/Midland/Mt. Pleasant broadcast belt.)
  g.MDCT.REGIONS = {
    se: 'SE Michigan', west: 'West Michigan',
    mid: 'Mid-Michigan', north: 'Northern Michigan', statewide: 'Statewide'
  };
  g.MDCT.COUNTY_REGION = (function () {
    var m = {}, add = function (region, list) { list.forEach(function (c) { m[c.toLowerCase()] = region; }); };
    add('se', ['Wayne', 'Oakland', 'Macomb', 'Washtenaw', 'Monroe', 'Livingston', 'St. Clair', 'St Clair', 'Lenawee']);
    add('west', ['Berrien', 'Cass', 'St. Joseph', 'St Joseph', 'Branch', 'Hillsdale', 'Van Buren',
      'Kalamazoo', 'Calhoun', 'Allegan', 'Barry', 'Ottawa', 'Kent', 'Ionia', 'Muskegon',
      'Montcalm', 'Newaygo', 'Oceana', 'Mecosta', 'Mason', 'Lake', 'Osceola']);
    // Mid-Michigan: former Capital-area counties (Lansing/Jackson) merged with the
    // Tri-Cities/Flint/Thumb belt — one region, matching TV/radio market identity.
    add('mid', ['Ingham', 'Clinton', 'Eaton', 'Jackson', 'Shiawassee', 'Gratiot',
      'Genesee', 'Saginaw', 'Midland', 'Bay', 'Isabella', 'Tuscola', 'Lapeer',
      'Sanilac', 'Huron', 'Arenac', 'Gladwin', 'Clare']);
    add('north', ['Oscoda', 'Ogemaw', 'Iosco', 'Roscommon', 'Missaukee', 'Wexford', 'Manistee',
      'Benzie', 'Grand Traverse', 'Leelanau', 'Kalkaska', 'Crawford', 'Antrim', 'Otsego',
      'Montmorency', 'Alpena', 'Alcona', 'Charlevoix', 'Emmet', 'Cheboygan', 'Presque Isle',
      'Mackinac', 'Luce', 'Chippewa', 'Schoolcraft', 'Delta', 'Alger', 'Marquette', 'Dickinson',
      'Menominee', 'Iron', 'Baraga', 'Houghton', 'Keweenaw', 'Ontonagon', 'Gogebic']);
    return m;
  })();
  g.MDCT.countyRegion = function (county) {
    if (!county) return 'statewide';
    var key = String(county).toLowerCase().replace(/\s+county$/, '').replace(/\s+co\.?$/, '').trim();
    return g.MDCT.COUNTY_REGION[key] || 'statewide';
  };
  g.MDCT.regionLabel = function (region) {
    return g.MDCT.REGIONS[region] || g.MDCT.REGIONS[g.MDCT.countyRegion(region)] || 'Statewide';
  };
  // Clean county chip label, e.g. "Lenawee Co."
  g.MDCT.countyLabel = function (county) {
    if (!county) return '';
    var c = String(county).replace(/\s+county$/i, '').replace(/\s+co\.?$/i, '').trim();
    return c ? c + ' Co.' : '';
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

  /* ---- Shareability + branding -------------------------------------------
     One branded share system for the whole site. Uses the OS native share
     sheet on mobile (social, text, email — everything), and a branded popover
     on desktop (X, Facebook, LinkedIn, copy link, text, email). Every share
     carries the Michigan Data Center Tracker name and links back to us.

     Usage: g.MDCT.share({ url, title, text });  // any arg optional
     Auto-wires any element with [data-share] (optional data-share-url /
     data-share-title), and drops a floating Share button on every page.     */
  g.MDCT.SITE = 'https://grahamandgold.github.io/mi-data-center-tracker/';
  g.MDCT.BRAND = 'Michigan Data Center Tracker';

  g.MDCT.share = function (opts) {
    opts = opts || {};
    var url = opts.url || (typeof location !== 'undefined' ? location.href : g.MDCT.SITE);
    var title = opts.title || (typeof document !== 'undefined' ? document.title : g.MDCT.BRAND);
    var text = opts.text || (title + ' — ' + g.MDCT.BRAND);
    if (typeof navigator !== 'undefined' && navigator.share) {
      navigator.share({ title: title, text: text, url: url }).catch(function () {});
      return;
    }
    g.MDCT._shareSheet(url, title, text);
  };

  g.MDCT._shareSheet = function (url, title, text) {
    var doc = document, enc = encodeURIComponent;
    var links = [
      ['X', 'https://twitter.com/intent/tweet?text=' + enc(text) + '&url=' + enc(url)],
      ['Facebook', 'https://www.facebook.com/sharer/sharer.php?u=' + enc(url)],
      ['LinkedIn', 'https://www.linkedin.com/sharing/share-offsite/?url=' + enc(url)],
      ['Text', 'sms:?&body=' + enc(text + ' ' + url)],
      ['Email', 'mailto:?subject=' + enc(title) + '&body=' + enc(text + '\n\n' + url)],
    ];
    var old = doc.getElementById('mdct-share-ov'); if (old) old.remove();
    var ov = doc.createElement('div'); ov.id = 'mdct-share-ov';
    ov.setAttribute('style', 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;');
    var card = doc.createElement('div');
    card.setAttribute('style', 'background:#16140f;border:1px solid #322e29;border-radius:8px;padding:22px;width:min(360px,90vw);font-family:Archivo,system-ui,sans-serif;');
    var rows = links.map(function (l) {
      return '<a href="' + l[1] + '" target="_blank" rel="noopener" data-close style="display:flex;align-items:center;justify-content:space-between;padding:11px 13px;margin:6px 0;background:#201a15;border:1px solid #2b2620;border-radius:5px;color:#f4f1ee;text-decoration:none;font-size:14px;">' + l[0] + '<span style="color:#E03131;">→</span></a>';
    }).join('');
    card.innerHTML =
      '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">' +
      '<img src="' + g.MDCT.SITE + 'brand-logo-nav.png" alt="' + g.MDCT.BRAND + '" style="height:22px;">' +
      '<span style="font-family:\'Space Mono\',monospace;font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:#8a847c;margin-left:auto;">Share</span></div>' +
      rows +
      '<button data-copy style="width:100%;margin-top:8px;padding:11px;background:#E03131;color:#fff;border:0;border-radius:5px;font-family:\'Space Mono\',monospace;font-size:12px;letter-spacing:.06em;text-transform:uppercase;cursor:pointer;">Copy link</button>';
    ov.appendChild(card); doc.body.appendChild(ov);
    ov.addEventListener('click', function (e) {
      if (e.target === ov || e.target.hasAttribute('data-close')) ov.remove();
      if (e.target.hasAttribute('data-copy')) {
        (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject())
          .then(function () { e.target.textContent = 'Copied ✓'; }, function () {});
      }
    });
  };

  g.MDCT.initShare = function () {
    if (typeof document === 'undefined' || document.getElementById('mdct-share-fab')) return;
    // wire explicit share triggers
    Array.prototype.forEach.call(document.querySelectorAll('[data-share]'), function (el) {
      el.style.cursor = 'pointer';
      el.addEventListener('click', function (e) {
        e.preventDefault();
        g.MDCT.share({ url: el.getAttribute('data-share-url') || location.href,
                       title: el.getAttribute('data-share-title') || document.title });
      });
    });
    // floating branded Share button (every page, every section reachable)
    var fab = document.createElement('button'); fab.id = 'mdct-share-fab';
    fab.setAttribute('aria-label', 'Share this page');
    fab.setAttribute('style', 'position:fixed;right:18px;bottom:18px;z-index:9998;display:flex;align-items:center;gap:8px;background:#E03131;color:#fff;border:0;border-radius:999px;padding:12px 18px;font-family:\'Space Mono\',monospace;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.4);');
    fab.innerHTML = '<span style="font-size:14px;">↗</span> Share';
    fab.addEventListener('click', function () { g.MDCT.share({}); });
    document.body.appendChild(fab);
  };

  if (typeof document !== 'undefined') {
    if (document.readyState !== 'loading') g.MDCT.initShare();
    else document.addEventListener('DOMContentLoaded', g.MDCT.initShare);
  }
})(typeof window !== 'undefined' ? window : globalThis);