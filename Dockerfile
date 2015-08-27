FROM centos:7

MAINTAINER Tomohisa Kusano <siomiz@gmail.com>

COPY main.py /

CMD ["/usr/bin/python", "/main.py"]

