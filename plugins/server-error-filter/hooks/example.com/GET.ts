Interceptor.attach({
  response: {
    onEnter(res, cfg) {
      if (res.status === undefined || res.status < 500 || res.status > 599) return;
      if (!res.body || typeof res.body !== 'object' || Array.isArray(res.body)) return;
      res.body.maintenance = true;
    },
    onLeave(res, cfg) {
      if (res.status === undefined || res.status < 500 || res.status > 599) return;
      const endpointId = cfg.endpoints?.preview;
      if (!endpointId) return;
      return { actions: [{ type: 'webhook', endpointId,
        json: { host: res.request.host!, status: res.status } }] };
    }
  }
});
