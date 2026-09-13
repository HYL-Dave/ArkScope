// Preview-only listener: keep the test guard's outbound TCP/DNS/UDP prohibitions.
const dns = require('node:dns');
const net = require('node:net');
const lookup = dns.lookup;
const listen = net.Server.prototype.listen;
require('./offline_node.cjs');
dns.lookup = function (host, ...args) {
  if (host !== '127.0.0.1') throw new Error('preview rejected non-loopback lookup');
  return lookup.call(this, host, ...args);
};
net.Server.prototype.listen = function (...args) {
  const host = typeof args[0] === 'object' ? args[0]?.host : args[1];
  if (host !== '127.0.0.1') throw new Error('preview rejected non-loopback listener');
  return listen.apply(this, args);
};
