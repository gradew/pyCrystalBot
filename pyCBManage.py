#!/usr/bin/python2

import httplib, urllib
import os, sys, ConfigParser

execPath = os.path.dirname(__file__)

config = ConfigParser.RawConfigParser()
config.read(execPath + '/pyCrystalBot.cfg')
web_host = config.get('web', 'host')
web_port = config.getint('web', 'port')


def sendCmd(host, cmd, args):
    params = urllib.urlencode(args)
    headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
    conn = httplib.HTTPConnection(host)
    conn.request("POST", "/" + cmd, params, headers)
    response = conn.getresponse()
    print(response.status, response.reason)
    data = response.read()
    print(data)
    conn.close()

if len(sys.argv)<3:
    print("Syntax: ./pyCBManage.py <command> <argument> [<argument>...]")
    sys.exit(1)

cmd = sys.argv[1]
arg = sys.argv[2]
dHost = web_host + ':' + str(web_port)

if cmd == 'modload' or cmd == 'modunload':
    sendCmd(dHost, cmd, { 'name': arg })
    sys.exit(0)

if cmd == 'raw':
    sendCmd(dHost, cmd, { 'raw': arg })
    sys.exit(0)

if cmd == 'say':
    if len(sys.argv) < 4:
        print("Not enough arguments")
        sys.exit(1)
    sendCmd(dHost, cmd, { 'dst': sys.argv[2], 'msg': sys.argv[3] })
    sys.exit(0)

print("Unknown command")

