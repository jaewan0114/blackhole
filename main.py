#!/usr/bin/python

# "tail" based on http://stackoverflow.com/a/12523302
# "2>/dev/null" based on http://stackoverflow.com/a/11269627

import threading, Queue, subprocess, re, os

tailq = Queue.Queue(maxsize=10)

def tail_forever():
    p = subprocess.Popen(
        ["/usr/bin/journalctl", "-D", "/var/log/journal", "_COMM=sshd", "-o", "cat", "-f"],
        stdout=subprocess.PIPE)
    while True:
        line = p.stdout.readline()
        tailq.put(line)
        if not line:
            break

threading.Thread(target=tail_forever).start()

while True:
    line = tailq.get()
    m = re.match('Invalid user .* from ([0-9\.]*)', line) \
        or re.match('User .* from ([0-9\.]*) not allowed', line) \
        or re.match('Connection closed by ([0-9\.]*) \[preauth\]', line) \
        or re.match('Received disconnect from ([0-9\.]*):.*\[preauth\]', line)
    if m:
        ipaddr = m.group(1)
        print "+ %s" % ipaddr
        with open(os.devnull, 'wb') as devnull:
            subprocess.call(["/usr/sbin/ip", "route", "add", "blackhole", ipaddr], stderr=devnull)

