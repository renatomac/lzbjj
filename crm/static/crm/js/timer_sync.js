// Only HTTP exchanges can estimate clock skew; realtime delivery has unknown latency.
window.timerClockFetch = async function (url, options = {}) {
    const sent = Date.now();
    const res = await fetch(url, { ...options, cache: 'no-store' });
    const data = await res.json();
    const arrived = Date.now();
    const received = Date.parse(data.server_received_at);
    const serverSent = Date.parse(data.server_time);
    if (res.ok && Number.isFinite(received) && Number.isFinite(serverSent)) {
        window.timerSkewOffset = ((received - sent) + (serverSent - arrived)) / 2;
    }
    return { res, data };
};
