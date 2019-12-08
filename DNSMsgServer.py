#!/usr/bin/env python3

# Copyright (c) 2019, Richard Hughes All rights reserved.
# Released under the BSD license. Please see LICENSE.md for more information.

import sys
import argparse
import base64
import datetime
import threading
import traceback
import socketserver
from dnslib import *


# Define command line arguments
parms=argparse.ArgumentParser()
parms.add_argument("-d", "--domain", type=str, required=True, help="Domain")
parms.add_argument("-p", "--port", type=int, required=False, default=53, help="Port to Listen On")
parms.add_argument("-i", "--ip", type=str, required=True, help="IP Address")
parms.add_argument("-l", "--listener", type=str, required=False, default="udp", choices=["udp","tcp","both"], help="Listener to Start")
args = vars(parms.parse_args())


# DomainName Class
class DomainName(str):
  def __getattr__(self, item):
    return DomainName(item + '.' + self)


# Define Parameters
D = DomainName(args['domain']+".")
IP = args['ip']
PORT = args['port']
TTL = 300


# SOA Record
soa = SOA(
  mname=D.ns1,    # Primamry name server
  rname=D.admin,  # Administrator's email
  times=(
    201307231,    # Serial
    3600,         # Refresh
    1800,         # Retry
    604800,       # Expire
    86400,        # Minimum TTL
  )
)


# NS Records
ns = [NS(D.ns1), NS(D.ns2)]


# DNS Records
records = {
  D: [A(IP), AAAA((0,) * 16), MX(D.mail), soa] + ns,
  D.ns1: [A(IP)], 
  D.ns2: [A(IP)],
  D.mail: [A(IP)],
  D.localhost: [A("127.0.0.1")],
}


# Process message
def procmsg(hostname):
  # Determine if this has a chance of being a valid message
  if((hostname[0:1] != "2" and hostname[0:1] != "4") or hostname.count("-") < 4):
    return

  # Split header elements.
  header=hostname.split("-")
  encoding=header[0]
  sender=header[1]
  timestamp=header[2]
  sequence=header[3]
  nummsgs, payload=header[4].split(".", 1)
  payload=payload[0:len(payload)-(len(args['domain'])+2)]
  payload=payload.replace(".","")

  # Set encoding type
  if(encoding == "2"):
    try:
      message=base64.b32decode(payload.upper())
    except:
      message=""
  elif(encoding == "4"):
    try:
      message=base64.b64decode(payload)
    except:
      message=""
  else:
    return

  try: 
    message=message.decode("utf-8")
    print(sender + "-" + message)
  except:
    message=""


# Base request handler
class BaseRequestHandler(socketserver.BaseRequestHandler):

  def get_data(self):
    raise NotImplementedError

  def send_data(self, data):
     raise NotImplementedError

  def handle(self):
    now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')

    try:
      data = self.get_data()
      self.send_data(dns_response(data))
    except Exception:
      #traceback.print_exc(file=sys.stderr)
      pass


# Handle DNS requests via TCP
class TCPRequestHandler(BaseRequestHandler):

    def get_data(self):
        data = self.request.recv(8192).strip()
        sz = int(data[:2].encode('hex'), 16)
        if sz < len(data) - 2:
            raise Exception("TCP packet to short")
        elif sz > len(data) - 2:
            raise Exception("TCP packet to long")
        return data[2:]

    def send_data(self, data):
        sz = hex(len(data))[2:].zfill(4).decode('hex')
        return self.request.sendall(sz + data)


# Handle DNS requests via UDP
class UDPRequestHandler(BaseRequestHandler):

    def get_data(self):
      return self.request[0].strip()

    def send_data(self, data):
      return self.request[1].sendto(data, self.client_address)


# Process DNS query
def dns_response(data):
  # Extract content from DNS query 
  request = DNSRecord.parse(data)
  qname = request.q.qname
  qn = str(qname)
  qtype = request.q.qtype
  qt = QTYPE[qtype]

  reply = DNSRecord(DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), q=request.q)
  if qn == D or qn.endswith('.' + D):
    # Process message in hostname
    if(qt == "TXT"):
      procmsg(qn)

    # Return specifi answer if available
    found=False
    for name, rrs in records.items():
      if name == qn:
        for rdata in rrs:
          rqt = rdata.__class__.__name__
          if qt in ['*', rqt]:
            reply.add_answer(RR(rname=qname, rtype=getattr(QTYPE, rqt), rclass=1, ttl=TTL, rdata=rdata))
            found=True
  
    # Send back a generic record if no specific record was found
    if(found == False):
      if(qt == "A"):
        reply.add_answer(RR(rname=qname, rtype=getattr(QTYPE, A(IP).__class__.__name__), rclass=1, ttl=TTL, rdata=A(IP)))
      if(qt == "TXT"): 
        now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
        reply.add_answer(RR(rname=qname, rtype=getattr(QTYPE, TXT(IP).__class__.__name__), rclass=1, ttl=TTL, rdata=TXT("OK "+now)))
   
    # Add NS recordss
    for rdata in ns:
      reply.add_ar(RR(rname=D, rtype=QTYPE.NS, rclass=1, ttl=TTL, rdata=rdata))

    # Add SOA record
    reply.add_auth(RR(rname=D, rtype=QTYPE.SOA, rclass=1, ttl=TTL, rdata=soa))
   
  return reply.pack()


# Main processing
def main(args):
  print("Starting DNSMsgServer.py")
  servers = []
  if(args['listener'] == 'udp' or args['listener'] == 'both'):
    servers.append(socketserver.ThreadingUDPServer(('', 53), UDPRequestHandler))
  if(args['listener'] == 'tcp' or args['listener'] == 'both'):
    servers.append(socketserver.ThreadingTCPServer(('', 53), TCPRequestHandler))

  for server in servers:
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    print("%s server loop started in thread: %s" % (server.RequestHandlerClass.__name__, thread.name))

  try:
    while 1:
      time.sleep(1)
      sys.stderr.flush()
      sys.stdout.flush()

  except KeyboardInterrupt:
    pass
  finally:
    print("")
    for server in servers:
      server.shutdown()
      print("%s server loop shutdown" % (server.RequestHandlerClass.__name__))


if __name__ == '__main__':
  # Execute main method
  main(args)
