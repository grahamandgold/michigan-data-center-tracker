/* Shared editorial helpers — loaded after content-data.js */
(function (g) {
  var MON = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];

  g.MDCT = g.MDCT || {};

  g.MDCT.ago = function (iso, now) {
    now = now || new Date();
    var h = Math.round((now - new Date(iso)) / 36e5);
    if (h < 1) return 'just now';
    if (h < 24) return h + 'h ago';
    var d = Math.round(h / 24);
    return d === 1 ? 'Yesterday' : d + 'd ago';
  };

  g.MDCT.recency = function (iso, now) {
    now = now || new Date();
    var h = (now - new Date(iso)) / 36e5;
    if (h <= 12) return { label: 'Breaking', cls: 'wire-tag-breaking', hot: true, breaking: true };
    if (h <= 36) return { label: 'Fresh', cls: 'wire-tag-fresh', hot: true, breaking: false };
    return { label: 'Latest', cls: '', hot: false, breaking: false };
  };

  g.MDCT.dateLabel = function (iso) {
    var d = new Date(iso);
    return MON[d.getMonth()] + ' ' + String(d.getDate()).padStart(2, '0');
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