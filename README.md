# DNSMsg
DNSMsgs enables you to send arbitrary messages through DNS servers and receive receipt confirmation.

There are applications out there that will do far more including tunneling TCP packets, however this was delveloped as a simple and lightweight tool to fulfil a particular need and is made available in case it proves useful to others.  By default the received messages are sent to the standard output stream but obvioulsy this can be customised for your particular use case.  For example you could forward messages to a chat app or MQTT server limited only by your imagination.

Future revisions will likley make the applicaiton extensible without changing the existing code and will certainly tidy up ugly elements that were a consequence of just getting somthing working. 

The software is made up of two applicaitons (DNSMsgServer and DNSMsgClient) and relies on the user having control of an authoritative DNS server where they will run DNSMsgServer to service requests from DNSMsgClient.

This is by no means an effecient method of sending messages but at times it may be the only way.

# License
DNSMsg is released under the BSD license. Please see [LICENSE.md](https://github.com/canidorichard/DNSMsg/blob/master/LICENSE.md) for more information.

# DNSMsgServer
Usage: python3 DNSMsgServer.py -d [domain]

DNSMsgServer must be run on an authoritative DNS server otherwise queries from DNSMsgClient will never arive.  It is possible to adapt the client to send queries direclty to the server but from experience this is rarely useful.  The purpose of DNSMsg was to get the message through when no direct internet access was availble by routing messages from DNS server to DNS server until they find their way home.

By default the DNSMsgServer will listen on UDP/53 but the port can be changed using "-p [port]".  The server will listen on TCP by specifying "-l tcp" or both TCP and UDP by specifying "-l both".  If you require a specific IP address to be returned in response to DNS queries then -i [ip] is what you are looking for.

The server can be requested to call an external application on receipt of each message by using "-c [cmd]".  If {id} and {msg} are placed in the command string then they will be substituded for the client id and the message.

# DNSMsgClient
Usage: python3 DNSMsgClient.py -d [domain] -m [message]

The client will send multiple DNS queries as required to accomodate the size of the message.
