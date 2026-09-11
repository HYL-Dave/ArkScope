const dns = require('node:dns');
const lookup = dns.lookup.bind(dns);
require('./offline_node.cjs');
const blocked = dns.lookup;
dns.lookup = (host, ...args) => host === '127.0.0.1'
  ? lookup(host, ...args) : blocked(host, ...args);
