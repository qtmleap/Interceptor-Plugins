/// <reference path="../types/interceptor.d.ts" />
const search: Interceptor.Match = { hosts: ['api.example.com'], methods: ['POST'], path: { kind: 'exact', value: '/search' } };

Interceptor.attach(search, {
  request: {
    onEnter(request) {
      if (!request.body || typeof request.body !== 'object' || Array.isArray(request.body)) return;
      request.body.limit = 5;
    }
  }
});

Interceptor.attach(search, {
  request: {
    onLeave(request, config) {
      const endpointId = config.endpoints?.preview;
      if (!endpointId) return;
      return {
        actions: [{
          type: 'webhook',
          endpointId,
          json: { summary: request.method + ' ' + request.host + request.path }
        }]
      };
    }
  }
});

Interceptor.attach(search, {
  response: {
    onEnter(response) {
      if (!response.body || typeof response.body !== 'object' || Array.isArray(response.body)) return;
      response.body.maintenance = true;
    }
  }
});

Interceptor.attach(search, {
  response: {
    onLeave(response, config) {
      const endpointId = config.endpoints?.preview;
      if (!endpointId) return;
      return {
        actions: [{
          type: 'webhook',
          endpointId,
          json: { path: response.request.path!, status: response.status! }
        }]
      };
    }
  }
});
