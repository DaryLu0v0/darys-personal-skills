/* Pure literature filtering helpers, shared by the browser and bounded tests. */
(function (root) {
  'use strict';
  function normalized(value) {
    return String(value ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();
  }
  function filterPapers(papers, {query = '', status = 'all', project = 'all', type = 'all'} = {}) {
    const needle = normalized(query).trim();
    return papers.filter(p => {
      const searchable = [p.title, ...(p.authors || []), p.year, p.doi, p.venue,
        ...(p.tags || []), ...(p.origins || []).flatMap(o => [o.source_id, o.record_id])];
      return (!needle || normalized(searchable.join(' ')).includes(needle)) &&
        (status === 'all' || (p.reading_status || 'metadata_only') === status) &&
        (type === 'all' || (p.type || 'unspecified') === type) &&
        (project === 'all' || (p.backlinks || []).some(b => b.project_id === project));
    }).sort((a, b) => a.title.localeCompare(b.title));
  }
  function obsidianOpenUri(target) {
    if (!target || typeof target.absolute_path !== 'string' || typeof target.uri !== 'string') return null;
    const path = target.absolute_path;
    if (!(/^[A-Za-z]:[\\/]/.test(path) || path.startsWith('/')) || /[\u0000-\u001f]/.test(path)) return null;
    try {
      const u = new URL(target.uri), keys = [...u.searchParams.keys()];
      if (u.protocol !== 'obsidian:' || u.hostname !== 'open' || u.pathname || u.hash || u.username || u.password || u.port) return null;
      if (keys.length !== 1 || keys[0] !== 'path' || u.searchParams.get('path') !== path) return null;
      return target.uri;
    } catch { return null; }
  }
  function checkpointPapers(papers, projectId, checkpointId) {
    return papers.flatMap(paper => {
      const contexts = (paper.backlinks || []).filter(b => b.project_id === projectId && b.checkpoint_id === checkpointId);
      return contexts.length ? [{paper, relevance:[...new Set(contexts.flatMap(b => b.relevance || []))].join('\n\n')}] : [];
    });
  }
  const api = {normalized, filterPapers, obsidianOpenUri, checkpointPapers};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.HikariLiterature = api;
})(typeof window !== 'undefined' ? window : this);
