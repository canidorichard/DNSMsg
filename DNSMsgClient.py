#!/usr/bin/env python3

# Copyright (c) 2019, Richard Hughes All rights reserved.
# Released under the BSD license. Please see LICENSE.md for more information.

import sys
import argparse
import base64
import socket
import uuid
import math
import datetime


max_dns_msg_len = 255

# Define command line arguments
parms=argparse.ArgumentParser()
parms.add_argument("-m", "--message", type=str, required=True, help="Message")
parms.add_argument("-d", "--domain", type=str, required=True, help="Domain")
args = vars(parms.parse_args())


# Main processing
def main(args):
  header_len = 16
  counter = 0
  tx_seq = 0x00
  msg_status = 0x30

  # Get bytes of MAC address
  mac = hex(uuid.getnode())[2:].upper()

  # Use millis in since last minute as unique counter value
  dt = datetime.datetime.now()
  counter = (dt.second * 1000) + int(dt.microsecond / 1000)

  # Calculate max payload size
  max_enc_payload_length = int((max_dns_msg_len - len(args['domain'])) - 4) # Allow for 4 label seperators
  max_dec_payload_length = int(max_enc_payload_length / 8) * 5 
  max_dec_message_length  = max_dec_payload_length - header_len

  # Generate messages
  bytesProcessed = 0
  while bytesProcessed < len(args['message']):
    endIndex = bytesProcessed + max_dec_message_length
    if(endIndex > len(args['message'])):
      endIndex = len(args['message'])
    # Set last message statua
    if(endIndex == len(args['message'])):
      msg_status = 0x31
    # Create header bytes
    counter_bytes = counter.to_bytes(2, 'little')
    header = bytearray(mac, encoding="utf-8")
    header.append(counter_bytes[0])
    header.append(counter_bytes[1])
    header.append(tx_seq)
    header.append(msg_status)
    tx_seq = tx_seq + 1
    # Create payload
    payload = header
    payload.extend(args['message'][bytesProcessed:endIndex].encode('utf-8'))
    # Base32 encode payload
    outBuf = base64.b32encode(payload)
    outBuf = outBuf.decode('utf-8').replace("=","0")
    bytesProcessed = endIndex
    # Add label seperators
    labelStart = 0
    labelSize = 63
    dnsmsg = ""
    while(labelStart < len(outBuf)):
      if(labelStart + labelSize > len(outBuf)):
        labelSize = len(outBuf) - labelStart
      dnsmsg = dnsmsg + outBuf[labelStart:labelStart+labelSize]
      labelStart = labelStart + labelSize
      dnsmsg = dnsmsg + "."
    dnsmsg = dnsmsg + args['domain']
    # Send message
    print("Sending DNS message: ", end='')
    ip = socket.gethostbyname(dnsmsg)
    print(ip)
    # Verify response
    ip_list = ip.split('.')
    if(int(ip_list[1]) != header[12] or int(ip_list[2]) != header[13] or int(ip_list[3]) != header[14]):
      print("Failed: Invalid response")
      sys.exit(1)


if __name__ == '__main__':
  # Execute main method 
  main(args)
