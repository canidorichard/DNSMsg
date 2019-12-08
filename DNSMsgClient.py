# Copyright (c) 2019, Richard Hughes All rights reserved.
# Released under the BSD license. Please see LICENSE.md for more information.

import sys
import argparse
import base64
import dns.resolver
import uuid
import math
import datetime


# Define command line arguments
parms=argparse.ArgumentParser()
parms.add_argument("-m", "--message", type=str, required=True, help="Message")
parms.add_argument("-e", "--encoding", type=str, required=False, default="base64", choices=['base32','base64'], help="Message Encoding")
parms.add_argument("-d", "--domain", type=str, required=True, help="Domain")
parms.add_argument("-s", "--sender", type=str, required=False, default=hex(uuid.getnode())[2:], help="Sender ID")
args = vars(parms.parse_args())


# Main processing
def main(args):
  # Set first part of header
  header1=""
  timestamp=format(int(datetime.datetime.utcnow().strftime('%H%M%S')), '01x')
  if(args['encoding'] == "base32"):
    header1="2-"
  else:
    header1="4-"
  header1=header1+args['sender']+"-"+timestamp+"-"

  # Calculate possible message length
  maxQueryLen=250
  maxHeader2Len=14 # 6 bytes Seq + 1 byte Seperator + 6 bytes Num Messages + 1 byte Seperator
  headerLen=len(header1)+maxHeader2Len
  domainLen=len(args['domain'])+1
  availableLen=maxQueryLen - headerLen - domainLen

  # Allow for encoding overhead
  if(args['encoding'] == "base32"):
    availableLen=int((availableLen/8)*5)
  else:
    availableLen=int((availableLen/8)*6)
  # Allow for label seperators
  availableLen=availableLen-4
 
  # Calculate how many queries are needed
  message=args['message']
  numMessages=math.ceil(len(message)/availableLen)

  # Split message into required queries
  header=""
  for seq in range(1, numMessages+1):

    # Compose message header
    header=header1+format(seq, '06x')+"-"+format(numMessages, '06x')+"."

    # Split message into query size chunks
    strpos=(seq-1)*availableLen
    msgpart=message[strpos:strpos+availableLen]

    # Enclode message part
    msgpart=msgpart.encode('utf-8')
    if(args['encoding'] == "base32"):
      msgpart=base64.b32encode(msgpart)
    else:
      msgpart=base64.b64encode(msgpart)
    msgpart=msgpart.decode('utf-8')
    
    # Split message part into labels
    labels=[msgpart[i:i+63] for i in range(0, len(msgpart), 63)]
    payload=""
    for label in labels:
      payload=payload+label+"."

    # Add header and domain to payload
    payload=header+payload+args['domain']

    # Send message
    if(query(payload) == False):
      sys.stderr.write("ERROR: Sent " + str(seq-1) + " of " + str(numMessages) + " queries\n")
      sys.exit(-1)

  print("Sent " + str(seq) + " of " + str(numMessages) + " queries")


# Send DNS query
def query(hostname):
  #print(hostname)
  try:
    answer=dns.resolver.query(hostname+".","TXT")
    if(str(answer[0])[1:3] == "OK"):
      return True
    else:
      return False
  except:
    return False


if __name__ == '__main__':
  # Execute main method 
  main(args)
