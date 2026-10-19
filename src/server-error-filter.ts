/// <reference path="../types/interceptor.d.ts" />
const serverError: Interceptor.Match = { hosts: ['example.com'], status: { min: 500, max: 599 } };

Interceptor.attach(serverError, {
  response: {
    onEnter(res, cfg) {
      if (!res.body || typeof res.body !== 'object' || Array.isArray(res.body)) return;
      res.body.maintenance = true;
    }
  }
});

Interceptor.attach(serverError, {
  response: {
    onLeave(res, cfg) {
      const endpointId = cfg.endpoints?.preview;
      if (!endpointId) return;
      return {
        actions: [{
          type: 'webhook',
          endpointId,
          json: { host: res.request.host!, status: res.status! }
        }]
      };
    }
  }
});
