/// <reference path="../types/interceptor.d.ts" />
const search: Interceptor.Match = { hosts: ['api.example.com'], methods: ['POST'], path: { kind: 'exact', value: '/search' } };

Interceptor.attach(search, {
  request: {
    onEnter(req, cfg) {
      if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)) return;
      req.body.limit = 5;
    }
  }
});

Interceptor.attach(search, {
  request: {
    onLeave(req, cfg) {
      const endpointId = cfg.endpoints?.preview;
      if (!endpointId) return;
      return {
        actions: [{
          type: 'webhook',
          endpointId,
          json: { summary: req.method + ' ' + req.host + req.path }
        }]
      };
    }
  }
});

Interceptor.attach(search, {
  response: {
    onEnter(res, cfg) {
      if (!res.body || typeof res.body !== 'object' || Array.isArray(res.body)) return;
      res.body.maintenance = true;
    }
  }
});

Interceptor.attach(search, {
  response: {
    onLeave(res, cfg) {
      const endpointId = cfg.endpoints?.preview;
      if (!endpointId) return;
      return {
        actions: [{
          type: 'webhook',
          endpointId,
          json: { path: res.request.path!, status: res.status! }
        }]
      };
    }
  }
});
