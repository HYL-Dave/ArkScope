// Test-runner guard only: mocked fetch works, real TCP/DNS/UDP must not escape.
const net = require('node:net');
const dns = require('node:dns');
const dgram = require('node:dgram');
const reject = () => { throw new Error('offline frontend check rejected network'); };
net.Socket.prototype.connect = reject;
dns.lookup = reject;
dns.resolve = reject;
dns.promises.lookup = async () => reject();
dns.promises.resolve = async () => reject();
dgram.Socket.prototype.send = reject;
