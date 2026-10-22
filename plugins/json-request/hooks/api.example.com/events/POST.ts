Interceptor.attach({
  request: {
    onLeave(req) {
      const body = req.body;
      if (!body || typeof body !== 'object' || Array.isArray(body)) return;
      const name = (body as { name?: unknown }).name;
      if (typeof name !== 'string') return;
      const record = { name: Array.from(name).slice(0, 64).join(''), source: (req.host ?? '') + (req.path ?? '') };
      const headers = { 'content-type': 'application/json' };
      Interceptor.send('create', { headers, json: record });
      Interceptor.send('replace', { headers, json: { latest: record } });
    }
  }
});
