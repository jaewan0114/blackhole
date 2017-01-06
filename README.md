# siomiz/blackhole

`ip route add blackhole` any IP address that failed SSH login and left a journal entry like:

    Invalid user .. from ..
    User .. from .. not allowed ..
    Received disconnect from .. .. [preauth]

Individual IP addresses will be immediately blocked.

ISP Subnet containing the IP address (according to corresponding WHOIS record) will be blocked on 3rd strike.

## Notes

* `/var/log/journal` is the default location of journal files on CoreOS / Container Linux; change as neccesary.
* `--net=host --cap-add=NET_ADMIN` is required for iptables from inside container to work

## systemd Service file example (working as of Container Linux 1235.4.0)

    [Unit]
    Description=Blackhole
    After=docker.service
    Requires=docker.service
    
    [Service]
    TimeoutStartSec=0
    ExecStartPre=-/usr/bin/docker kill blackhole
    ExecStartPre=-/usr/bin/docker rm blackhole
    ExecStartPre=/usr/bin/docker pull siomiz/blackhole
    ExecStart=\
    /usr/bin/docker run \
      --name blackhole \
      --net=host \
      --cap-add=NET_ADMIN \
      -v /var/log/journal:/var/log/journal:ro \
      -v /usr/bin/journalctl:/usr/bin/journalctl:ro \
      -v /lib64:/usr/local/lib64:ro \
      -v /lib64/libgcrypt.so.20:/usr/lib64/libgcrypt.so.20:ro \
      -v /lib64/libgpg-error.so.0:/usr/lib64/libgpg-error.so.0:ro \
      -v /usr/lib64/systemd/libsystemd-shared-231.so:/lib64/libsystemd-shared-231.so:ro \
      -v /usr/lib64/libseccomp.so.2:/lib64/libseccomp.so.2:ro \
      siomiz/blackhole
    ExecStop=/usr/bin/docker stop blackhole
    
    [Install]
    WantedBy=multi-user.target
