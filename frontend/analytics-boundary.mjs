const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function shouldEmitLandingEvent(config, pageLocation) {
  return config?.deployment === "production" && config?.landingAnalyticsEnabled === true &&
    pageLocation?.protocol === "https:" && !LOCAL_HOSTS.has(String(pageLocation.hostname || "").toLowerCase());
}
