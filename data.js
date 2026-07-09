/* THE DATA — searchable project database. Reads map-data.json (the same source
   of truth as the live map). No numbers are invented here; blanks stay blank. */
(function () {
  'use strict';

  var REGION = {
    metro: ['Wayne', 'Oakland', 'Macomb', 'Washtenaw', 'Monroe', 'Livingston', 'Lenawee', 'St. Clair'],
    west: ['Kent', 'Ottawa', 'Kalamazoo', 'Allegan', 'Muskegon', 'Berrien', 'Van Buren', 'Calhoun', 'Barry', 'Ionia', 'Cass', 'Branch', 'St. Joseph'],
    mid: ['Ingham', 'Jackson', 'Genesee', 'Saginaw', 'Bay', 'Midland', 'Isabella', 'Clinton', 'Eaton', 'Shiawassee', 'Gratiot', 'Clare', 'Mecosta', 'Mt. Pleasant']
  };
  var REGION_LABEL = { metro: 'SE Michigan', west: 'West Michigan', mid: 'Mid-Michigan', north: 'Northern Michigan' };
  function regionFor(county) {
    county = (county || '').replace(/ County$/, '').trim();
    for (var r in REGION) if (REGION[r].indexOf(county) !== -1) return r;
    return 'north';
  }

  var STATUS_COLOR = {
    'Under construction': '#d98a2b', 'Approved': '#cf2431', 'Conditionally approved': '#cf5a2b',
    'Proposed': '#c9a227', 'Under review': '#c9a227', 'Withdrawn': '#8a847c', 'Rejected by planning commission': '#8a847c'
  };
  function statusColor(s) { return STATUS_COLOR[s] || '#8a847c'; }
  function parseMW(v) { var n = parseFloat(String(v == null ? '' : v).replace(/[^0-9.]/g, '')); return isNaN(n) ? null : n; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  var rows = [], state = { q: '', status: '', region: '', sort: 'mw', dir: -1 };

  function load() {
    fetch('map-data.json?v=' + Date.now()).then(function (r) { return r.json(); }).then(function (d) {
      var pts = (d && d.map_points) || [];
      rows = pts.filter(function (p) { return p.layer === 'projects'; }).map(function (p) {
        var reg = regionFor(p.county);
        return {
          name: p.name || '', place: [p.municipality, (p.county ? p.county + ' Co.' : '')].filter(Boolean).join(', '),
          region: reg, regionLabel: REGION_LABEL[reg], status: p.status || '—', developer: p.developer || '—',
          mw: parseMW(p.power_mw), mwText: p.power_mw || '', note: p.note || '',
          source_url: p.source_url || '', source_name: p.source_name || 'source',
          confidence: p.confidence || '', county: p.county || '', municipality: p.municipality || ''
        };
      });
      buildFilters(); buildStats(); render();
      var up = d.updated || d.updated_at || '';
      if (up) document.getElementById('db-updated').textContent = 'Records last verified ' + up + ' · sourced from public filings, news, and official releases.';
    }).catch(function (e) {
      document.getElementById('db-body').innerHTML = '<tr><td colspan="7" class="db-empty">Could not load the data (' + esc(e.message) + ').</td></tr>';
    });
  }

  function buildFilters() {
    var st = {}, rg = {};
    rows.forEach(function (r) { st[r.status] = 1; rg[r.region] = 1; });
    var ss = document.getElementById('db-status');
    Object.keys(st).sort().forEach(function (s) { var o = document.createElement('option'); o.value = s; o.textContent = s; ss.appendChild(o); });
    var rs = document.getElementById('db-region');
    ['metro', 'west', 'mid', 'north'].filter(function (r) { return rg[r]; }).forEach(function (r) {
      var o = document.createElement('option'); o.value = r; o.textContent = REGION_LABEL[r]; rs.appendChild(o);
    });
  }

  function buildStats() {
    var total = rows.length;
    var mw = rows.reduce(function (a, r) { return a + (r.mw || 0); }, 0);
    var active = rows.filter(function (r) { return /Proposed|Under review|Conditionally/.test(r.status); }).length;
    var built = rows.filter(function (r) { return /Under construction|^Approved/.test(r.status); }).length;
    var gw = (mw / 1000);
    var stats = [
      { n: total, l: 'Tracked projects' },
      { n: (gw >= 1 ? gw.toFixed(1) : (mw ? mw.toLocaleString() : '—')), u: (gw >= 1 ? 'GW' : (mw ? 'MW' : '')), l: 'Disclosed load' },
      { n: active, l: 'Active proposals' },
      { n: built, l: 'Approved / building' }
    ];
    document.getElementById('db-stats').innerHTML = stats.map(function (s) {
      return '<div class="db-stat"><div class="n">' + esc(s.n) + (s.u ? '<span class="u">' + s.u + '</span>' : '') + '</div><div class="l">' + esc(s.l) + '</div></div>';
    }).join('');
  }

  function filtered() {
    var q = state.q.toLowerCase();
    var out = rows.filter(function (r) {
      if (state.status && r.status !== state.status) return false;
      if (state.region && r.region !== state.region) return false;
      if (q) {
        var hay = (r.name + ' ' + r.developer + ' ' + r.municipality + ' ' + r.county).toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
    var k = state.sort, dir = state.dir;
    out.sort(function (a, b) {
      var va = a[k], vb = b[k];
      if (k === 'mw') { va = va == null ? -1 : va; vb = vb == null ? -1 : vb; return (va - vb) * dir; }
      if (k === 'place') { va = a.county; vb = b.county; }
      va = String(va || '').toLowerCase(); vb = String(vb || '').toLowerCase();
      return va < vb ? -dir : va > vb ? dir : 0;
    });
    return out;
  }

  function render() {
    var list = filtered();
    var body = document.getElementById('db-body');
    document.getElementById('db-count').innerHTML = 'Showing <b>' + list.length + '</b> of ' + rows.length;
    if (!list.length) { body.innerHTML = '<tr><td colspan="7" class="db-empty">No projects match those filters.</td></tr>'; return; }
    body.innerHTML = list.map(function (r) {
      var c = statusColor(r.status);
      return '<tr>' +
        '<td><span class="db-name">' + esc(r.name) + '</span>' + (r.note ? '<span class="db-note">' + esc(r.note) + '</span>' : '') + '</td>' +
        '<td>' + esc(r.place || '—') + '</td>' +
        '<td>' + esc(r.regionLabel) + '</td>' +
        '<td><span class="db-pill" style="color:' + c + ';border-color:' + c + '66;background:' + c + '18;">' + esc(r.status) + '</span></td>' +
        '<td>' + esc(r.developer) + '</td>' +
        '<td class="db-mw">' + (r.mwText ? esc(r.mwText) + ' MW' : '<span style="color:#5a554f;">—</span>') + '</td>' +
        '<td class="db-src">' + (r.source_url ? '<a href="' + esc(r.source_url) + '" target="_blank" rel="noopener">' + esc(r.source_name) + ' ↗</a>' : '—') + (r.confidence ? '<div class="db-conf">' + esc(r.confidence) + '</div>' : '') + '</td>' +
        '</tr>';
    }).join('');
  }

  function wire() {
    var q = document.getElementById('db-q'); if (q) q.addEventListener('input', function () { state.q = q.value; render(); });
    var ss = document.getElementById('db-status'); if (ss) ss.addEventListener('change', function () { state.status = ss.value; render(); });
    var rs = document.getElementById('db-region'); if (rs) rs.addEventListener('change', function () { state.region = rs.value; render(); });
    document.querySelectorAll('th[data-sort]').forEach(function (th) {
      th.addEventListener('click', function () {
        var k = th.getAttribute('data-sort');
        if (state.sort === k) state.dir = -state.dir; else { state.sort = k; state.dir = (k === 'mw') ? -1 : 1; }
        document.querySelectorAll('th[data-sort] .ar').forEach(function (a) { a.remove(); });
        var ar = document.createElement('span'); ar.className = 'ar'; ar.textContent = state.dir > 0 ? '▲' : '▼'; th.appendChild(ar);
        render();
      });
    });
  }

  if (document.readyState !== 'loading') { wire(); load(); }
  else document.addEventListener('DOMContentLoaded', function () { wire(); load(); });
})();
