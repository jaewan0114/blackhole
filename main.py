#!/usr/bin/python

# "tail" based on http://stackoverflow.com/a/12523302
# "2>/dev/null" based on http://stackoverflow.com/a/11269627

import threading, Queue, subprocess, re, os, signal, sys

tailq = Queue.Queue(maxsize=10)
state = []

class Subnet(object):
    cidr = '0.0.0.0/0'
    binary = '0' * 32
    size = 0

    def __init__(self, cidr):
        # self.cidr = cidr
        self.binary = Subnet.bits(cidr.split('/')[0])
        self.size = int(cidr.split('/')[1])

        # normalize, ex. 10/8 to 10.0.0.0/8
        self.cidr = Subnet.bin2cidr(self.binary, self.size)

    def __repr__(self):
        return '<Subnet %s>' % self.cidr

    def __cmp__(self, other):
        return other.size - self.size

    def __eq__(self, other):
        return self.cidr == other.cidr

    def contains(self, other):
        if self <= other:
            return False
        return self.binary[:self.size] == other.binary[:self.size]

    @classmethod
    def bin2char(cls, b):
        c = 0
        b = b[::-1]
        for i in range(8):
            c += (2 ** i) if b[i] == '1' else 0
        return c

    @classmethod
    def bin2cidr(cls, b, p):
        r = []
        for i in range(4):
            r.append(str(Subnet.bin2char(b[i * 8:i * 8 + 8])))
        return '%s/%d' % ('.'.join(r), p)

    @classmethod
    def bits(cls, ipaddr):
        n = 0
        r = []
        for s in ipaddr.split('.'):
            r.append('{:08b}'.format(int(s)))
        return ''.join(r).ljust(32, '0')

    @classmethod
    def from_range(cls, lo, hi):

        blo = Subnet.bits(lo)
        bhi = Subnet.bits(hi)

        p = 0
        for i in range(32):
            if blo[i] == bhi[i]:
                p += 1
            else:
                break
        s = blo[0:p] + ('0' * 32)

        return cls(Subnet.bin2cidr(s, p))

    @classmethod
    def from_ipaddr(cls, ipaddr):

        return cls('%s/32' % ipaddr)


class Block(object):
    subnet = None
    left = 0
    engaged = False

    def __repr__(self):
        return '[%s Block %s]' % \
            ('Engaged' if self.engaged else 'Pending', self.subnet)

    def __init__(self, subnet, left=1):
        self.subnet = subnet
        self.left = left
        self.strike()

    def __eq__(self, other):
        return self.subnet == other.subnet

    def strike(self):
        if self.engaged:
            return

        self.left -= 1
        print '  %s: %d left' % (self, self.left)
        if self.left <= 0:
            self.engage()

    def __del__(self):
        if self.engaged:
            self.iproute(['delete', 'blackhole', self.subnet.cidr])

    def engage(self):
        self.iproute(['add', 'blackhole', self.subnet.cidr])
        self.engaged = True
        print '      %s' % self

    def iproute(self, cmd=[]):
        cmd = ['ip', 'route'] + cmd
        print '    calling: %s' % ' '.join(cmd)
        try:
            with open(os.devnull, 'wb') as devnull:
                subprocess.call(cmd, stderr=devnull)
        except Exception, e:
            print e


def whois(refer, ipaddr):
    lines = ''
    new_refer = False
    subnets = []

    try:
        lines = subprocess.check_output(['/usr/bin/whois', '-h', refer, ipaddr], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError, e:
        lines = e.output

    for line in lines.split('\n'):
        line = line.lower()
        if line.startswith('refer:'):
            m = re.findall(r'[^:\t\ ]+$', line)
            if m:
                new_refer = m[0]
        if line.startswith('inetnum:') or line.startswith('cidr'):
            m = re.findall(r'[\d\.]+\/\d{1,2}', line)
            if m:
                for cidr in m:
                    subnets.append(Subnet(cidr))
            else:
                m = re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', line)
                if len(m) == 2:
                    subnets.append(Subnet.from_range(m[0], m[1]))

    if new_refer:
        return whois(new_refer, ipaddr)
    else:
        return subnets


def blackhole(ipaddr):
    global state

    subnets = whois('whois.iana.org', ipaddr)

    single = Subnet.from_ipaddr(ipaddr)
    skip = False

    for b in state:
        if b.subnet.contains(single) and b.engaged:
            skip = True
            print '  %s contains %s' % (b, single)
        elif b.subnet == single and b.engaged:
            skip = True
            print '  %s exists' % b

    if not skip:
        state.append(Block(single))

        if subnets:
            s = min(subnets)
            nb = next((ib for ib in state if ib.subnet == s), None)
            if nb:
                nb.strike()
                if nb.engaged:
                    for b in state:
                        if b != nb and nb.subnet.contains(b.subnet):
                            print '  consolidating %s' % b
                            state.remove(b)
            else:
                state.append(Block(s, left=3))


def tail_forever():
    try:
        p = subprocess.Popen(
            ["/usr/bin/journalctl", "-D", "/var/log/journal", "_COMM=sshd", "-o", "cat", "-f", "-n", "100"],
            stdout=subprocess.PIPE)
        while True:
            line = p.stdout.readline()
            tailq.put(line)
            if not line:
                break
    finally:
        p.terminate()


def sigterm_handler(sig, frame):
    sys.exit()


signal.signal(signal.SIGTERM, sigterm_handler)

th = threading.Thread(target=tail_forever)
th.start()

try:
    while True:
        line = tailq.get()
        m = re.match('Invalid user .* from ([0-9\.]*)', line) \
            or re.match('User .* from ([0-9\.]*) not allowed', line) \
            or re.match('Received disconnect from ([0-9\.]*):.*\[preauth\]', line) \
            or re.match('Failed password for .* from ([0-9\.]*) port [0-9]+ ssh2', line) \
            or re.match('Did not receive identification string from ([0-9\.]*)', line)
        if m:
            ipaddr = m.group(1)
            print
            print ipaddr
            blackhole(ipaddr)
except Exception, e:
    print e
finally:
    print
    print 'cleaning up'
    while True:
        try:
            b = state.pop()
            del b
        except:
            break
    th.join()

