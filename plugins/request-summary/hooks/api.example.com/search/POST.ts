Interceptor.attach({
  request: {
    onEnter(req, cfg) {
      if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)) return;
      req.body.limit = 5;
    },
    onLeave(req, cfg) {
      const endpointId = cfg.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{ type: 'webhook', endpointId,
        json: { summary: req.method + ' ' + req.host + req.path } }] };
    }
  },
  response: {
    onEnter(res, cfg) {
      if (!res.body || typeof res.body !== 'object' || Array.isArray(res.body)) return;
      res.body.maintenance = true;
    },
    onLeave(res, cfg) {
      const endpointId = cfg.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{ type: 'webhook', endpointId,
        json: { path: res.request.path!, status: res.status! } }] };
    }
  }
});
