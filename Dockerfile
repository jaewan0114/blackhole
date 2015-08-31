FROM centos:7

MAINTAINER Tomohisa Kusano <siomiz@gmail.com>

RUN yum install -y whois

COPY main.py /

CMD ["/usr/bin/python", "/main.py"]

