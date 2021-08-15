
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
import subprocess
from queue import Queue


# Define command line arguments
parms=argparse.ArgumentParser()
parms.add_argument("-d", "--domain", type=str, required=True, help="Domain")
parms.add_argument("-i", "--ip", type=str, required=False, default="127.0.0.1", help="IP Address")
parms.add_argument("-l", "--listener", type=str, required=False, default="udp", choices=["udp","tcp","both"], help="Listener to Start")
parms.add_argument("-c", "--cmd", type=str, required=False, default="", help="Command to process each message passing {id} and {msg}")
args = vars(parms.parse_args())


# Globals
cmdqueue=Queue()
shutdown = False


# DomainName Class
class DomainName(str):
  def __getattr__(self, item):
    return DomainName(item + '.' + self)


# Define Parameters
D = DomainName(args['domain']+".")
IP = args['ip']
TTL = 60


# SOA Record
soa = SOA(
  mname=D.ns1,    # Primamry name server
  rname=D.admin,  # Administrator's email
  times=(
    201307231,    # Serial
    3600,         # Refresh
    1800,         # Retry
    604800,       # Expire
    86400,        # Negative Cache (Previoulsy minimum TTL)
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
}


# Process message
def procmsg(hostname):
  global IP
  # Remove label seperators and domain name
  hostname = hostname[0:len(hostname) - (len(args['domain'])+2)]
  hostname = hostname.replace("0", "=")
  hostname = hostname.replace(".", "")
  # Attempt to decode message
  try:
    payload=base64.b32decode(hostname.upper())
    id = payload[0:12].decode('utf-8')
    msg = payload[16:].decode('utf-8')
    # Return countert and transmission sequence as IP address
    IP="1." + str(payload[12]) + "." + str(payload[13]) + "." + str(payload[14])
  except:
    # Message could not be decoded
    return
  # Add external message handler call to the queue.
  if(args['cmd'] != ""):
    cmdline = args['cmd'].replace("{id}", id)
    cmdline = cmdline.replace("{msg}", msg)
    cmdqueue.put(cmdline)
  # Print message to standard out
  print(id + "|" + msg)


# Base request handler
class BaseRequestHandler(socketserver.BaseRequestHandler):
  def get_data(self):
    raise NotImplementedError

  def send_data(self, data):
     raise NotImplementedError

  def handle(self):
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
  procresp = "FALSE"

  reply = DNSRecord(DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), q=request.q)
  if qn == D or qn.endswith('.' + D):
    # Check if we have a message in the hostname
    procmsg(qn)

    # Return specific answer if available
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
        reply.add_answer(RR(rname=qname, rtype=getattr(QTYPE, TXT(IP).__class__.__name__), rclass=1, ttl=TTL, rdata=TXT(procresp)))
   
    # Add NS recordss
    for rdata in ns:
      reply.add_ar(RR(rname=D, rtype=QTYPE.NS, rclass=1, ttl=TTL, rdata=rdata))

    # Add SOA record
    reply.add_auth(RR(rname=D, rtype=QTYPE.SOA, rclass=1, ttl=TTL, rdata=soa))
   
  return reply.pack()


# External message handler
def ExtMessageHandler():
  while not shutdown:
    while not cmdqueue.empty():
        c=cmdqueue.get_nowait()
        # Use subprocess.call if Python version < 3.5
        rc=0
        if sys.version_info[0] > 5:
          rc=subprocess.call(c,shell=True)
        else:
          p=subprocess.run(c,shell=True)
          rc=p.returncode
        if not rc == 0:
          print("Error executing command: " + c + " (" + rc + ")")
    time.sleep(1)


# Main processing
def main(args):
  global shutdown
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
    print("%s server started in thread: %s" % (server.RequestHandlerClass.__name__, thread.name))
  extMessageThread = threading.Thread(target=ExtMessageHandler)
  extMessageThread.start() 
  print("External message handler started in thread: %s" % extMessageThread.name)

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
      print("%s server shutdown" % (server.RequestHandlerClass.__name__))
    shutdown=True
    extMessageThread.join()
    print("External message handler thread shutdown")


if __name__ == '__main__':
  # Execute main method
  main(args)
