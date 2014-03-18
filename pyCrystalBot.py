#!/usr/bin/python2

import socket
import os, sys, re, datetime, ConfigParser
import threading
from flask import Flask, render_template, request
import json

import logging

app = Flask(__name__)

users = {}
usersLock = threading.Lock()

mySocket = None
socketFile = None
socketWriteLock = threading.Lock()

log_path = None
execPath = os.path.dirname(__file__)

moduleHash = { }

sys.path.append(execPath + "/modules/")

def sendToSocket(msg):
    socketWriteLock.acquire()
    mySocket.send(msg+"\r\n")
    socketWriteLock.release()

class pyCrystalWebServer:
    bind_host = None
    bind_port = None

    def __init__(self, host_='0.0.0.0', port_=5000):
        self.bind_host = host_
        self.bind_port = port_

    def start(self):
        # Start thread
        t1 = threading.Thread(target=self.threadWebServer)
        t1.daemon = True
        t1.setDaemon(True)
        t1.start()

    def threadWebServer(self):
        #self.log("Thread started")
        app.run(host=self.bind_host, port=self.bind_port)

    @app.route("/")
    def getRoot():
        return render_template("index.html")

    @app.route("/users", methods=['GET'])
    def getUsers():
        res = { }
        usersLock.acquire()
        for userKey in users:
            user = users[userKey]
            res[userKey] = user
        usersLock.release()
        return render_template("userdump.html", users=res)
        #return json.dumps(res)

    @app.route('/say', methods=['POST'])
    def sayTo():
        mDst = request.form["dst"]
        mMsg = request.form["msg"]
        if re.match('^[^\s]+$', mDst):
            sendToSocket("PRIVMSG %s :%s" % (mDst, mMsg))
        return ""

    @app.route('/raw', methods=['POST'])
    def rawMsg():
        mRaw = request.form['raw']
        sendToSocket(mRaw)
        return ""

    @app.route('/mode', methods=['POST'])
    def modeMsg():
        mChan = request.form['channel']
        mModes = request.form['modes']
        mTargets = request.form['targets']
        sendToSocket("MODE %s %s %s" % (mChan, mModes, mTargets))
        return ""

    @app.route('/kick', methods=['POST'])
    def kickMsg():
        mChan = request.form['channel']
        mTarget = request.form['target']
        mReason = request.form['reason']
        sendToSocket("KICK %s %s :%s" % (mChan, mTarget, mReason))
        return ""

class pyCrystalBot:
    connected = False
    host = ''
    port = ''
    ssl = 0
    myNick = ''
    myIdent = ''
    nickserv_pass = ''
    channels = [ ]

    regex_ping = re.compile('^PING :(.+)$')
    regex_nick = re.compile('^:([^\s]+)!([^\s]+)@([^\s]+) NICK :(.+)$')

    regex_class2 = re.compile('^:([^ ]+) MODE ([^ ]+) :(.+)$')
    regex_class2_invite = re.compile('^:([^ ]+) INVITE ([^ ]+) :(.+)$')

    regex_class3 = re.compile('^:([^ ]+) ([0-9]+ .+)\s*$')
    regex_class3_names = re.compile('^353 ([^ ]+) . ([^ ]+) :(.+)$')
    regex_class3_nick = re.compile('^433 (.+)$')
    regex_class3_who = re.compile('^352 [^ ]+ (#[^ ]+) ([^ ]+) ([^ ]+) ([^ ]+) ([^ ]+) ([^ ]+) [^ ]+ (.+)$')
    regex_class3_whois = re.compile('^311 [^ ]+ ([^ ]+) ([^ ]+) ([^ ]+) [^ ]+ :(.+)$')
    regex_class3_motdend = re.compile('^376(.+)$')
    regex_class3_banned = re.compile('^474 ([^ ]+) ([^ ]+) :(.+)$')

    regex_class4 = re.compile('^:([^!]+)!([^@]+)@([^ ]+) ([^ ]+ .+)\s*$')
    regex_class4_part = re.compile('^PART (#[^ ]+)( :.+)?$')
    regex_class4_quit = re.compile('^QUIT :(.+)$')
    regex_class4_join = re.compile('^JOIN :(.+)$')
    regex_class4_nick = re.compile('^NICK :(.+)$')
    regex_class4_notice = re.compile('^NOTICE ([^ ]+) :(.+)$')
    regex_class4_privmsg = re.compile('^PRIVMSG ([^ ]+) :(.+)$')
    regex_class4_kick = re.compile('^KICK ([^ ]+) ([^ ]+) :(.+)$')
    regex_class4_mode = re.compile('^MODE ([^ ]+) ([^ ]+) ?(.+)?$')
    regex_class4_kill = re.compile('^KILL ([^ ]+) :(.+)$')

    regex_class5 = re.compile('^:([^@! ]+) MODE (#[^ ]+) ([\+\-a-z]+) (.+)$')

    regex_prefixed_nick = re.compile('^([\+%@])([^\s]+)$')

    def __init__(self, _nick, _ident, _gecos, _host, _port, _ssl, _join, _nickserv_pass):
        self.myNick = _nick.strip()
        self.myIdent = _ident.strip()
        self.myGecos = _gecos.strip()
        self.host = _host.strip()
        self.port = _port
        self.ssl = _ssl
        self.nickserv_pass = _nickserv_pass.strip()

        words = _join.split(',')
        for word in words:
            self.channels.append(word.strip())

    def run(self):
        global mySocket
        mySocket = socket.socket()
        mySocket.connect((self.host, self.port))
        socketFile = mySocket.makefile()
        self.send("NICK %s" % self.myNick)
        self.send("USER %(ident)s %(nick)s %(nick)s :%(gecos)s" % {'nick':self.myNick, 'ident':self.myIdent, 'gecos':self.myGecos})

        while True:
            data = socketFile.readline().strip()
            if data == '':
                continue
            self.process(data)

    def loadModule(self, name):
        if name in moduleHash:
            return False, "Module already loaded"
        fileName = name
        try:
            module = __import__(fileName, fromlist=[])
        except:
            return False, "Could not load module!"
        moduleHash[name] = module.pyCBModule(self)
        return True, ""

    def unloadModule(self, name):
        if name not in moduleHash:
            return False, "Module not loaded"
        del moduleHash[name]
        return True, ""

    def log(self, msg):
        logging.debug("[%s] %s" % (datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"), msg))

    def userDelete(self, nick):
        if nick.lower() in users:
            usersLock.acquire()
            del users[nick.lower()]
            usersLock.release()

    def userAddUpdate(self, nick, ident, host, gecos=None):
        lNick = nick.lower()
        usersLock.acquire()
        if not lNick in users:
            users[lNick] = {}
            users[lNick]['gecos'] = ''
            users[lNick]['channels'] = { }
        user = users[lNick]
        user['nick'] = nick
        user['ident'] = ident
        user['host'] = host
        if gecos != None:
            user['gecos'] = gecos
        usersLock.release()

    def userRename(self, oldNick, newNick):
        usersLock.acquire()
        lOldNick = oldNick.lower()
        lNewNick = newNick.lower()
        if lOldNick in users:
            userData = users[lOldNick]
            users[lNewNick] = userData
            users[lNewNick]['nick'] = newNick
        usersLock.release()

    def userAddChannel(self, nick, channel):
        usersLock.acquire()
        lNick = nick.lower()
        lChannel = channel.lower()
        if lNick in users:
            channels = users[lNick]['channels']
            if not (lChannel in channels):
                channels[lChannel] = { }
                channels[lChannel]['voice'] = 0
                channels[lChannel]['halfop'] = 0
                channels[lChannel]['op'] = 0
                channels[lChannel]['admin'] = 0
                channels[lChannel]['owner'] = 0
        usersLock.release()

    def userRemoveChannel(self, nick, channel):
        usersLock.acquire()
        lNick = nick.lower()
        lChannel = channel.lower()
        if lNick in users:
            channels = users[lNick]['channels']
            if lChannel in channels:
                del channels[lChannel]
        usersLock.release()

    def userSetChannelModes(self, nick, chan, modes):
        self.log("userSetChannelModes(%s, %s, %s)" % (nick, chan, modes))
        lNick = nick.lower()
        lChan = chan.lower()
        usersLock.acquire()
        if not lNick in users:
            usersLock.release()
            return
        channels = users[lNick]['channels']
        if not lChan in channels:
            usersLock.release()
            return
        matchedPositive = re.match('\+([^\-]+)', modes)
        matchedNegative = re.match('\-([^\+]+)', modes)
        posFlags = ''
        negFlags = ''
        if matchedPositive:
            posFlags = matchedPositive.group(1)
        if matchedNegative:
            negFlags = matchedNegative.group(1)
        if 'v' in posFlags: channels[lChan]['voice'] = 1
        if 'h' in posFlags: channels[lChan]['halfop'] = 1
        if 'o' in posFlags: channels[lChan]['op'] = 1
        if 'a' in posFlags: channels[lChan]['admin'] = 1
        if 'q' in posFlags: channels[lChan]['owner'] = 1
        if 'v' in negFlags: channels[lChan]['voice'] = 0
        if 'h' in negFlags: channels[lChan]['halfop'] = 0
        if 'o' in negFlags: channels[lChan]['op'] = 0
        if 'a' in negFlags: channels[lChan]['admin'] = 0
        if 'q' in negFlags: channels[lChan]['owner'] = 0
        usersLock.release()

    def process(self, data):
        # handle ping pong
        match = self.regex_ping.match(data)
        if match:
            self.send('PONG :' + match.group(1))
            if self.connected == False:
                self.perform()
                self.connected = True
            return

        self.log("S< %s" % data)
        # Class 3
        match = self.regex_class3.match(data)
        if match:
            self.process_class3(match.group(1), match.group(2))
            return
        # Class 4
        match = self.regex_class4.match(data)
        if match:
            self.process_class4(match.group(1), match.group(2), match.group(3), match.group(4))
            return

    def process_class3(self, server, remainder):
        # NAMES
        match = self.regex_class3_names.match(remainder)
        if match:
            nDest = match.group(1)
            nChannel = match.group(2)
            self.send('WHO '+nChannel)
            return
        # WHO
        match = self.regex_class3_who.match(remainder)
        if match:
            wChan = match.group(1)
            wIdent = match.group(2)
            wHost = match.group(3)
            wServer = match.group(4)
            wNick = match.group(5)
            wFlags = match.group(6)
            wGecos = match.group(7)
            self.userAddUpdate(wNick, wIdent, wHost, wGecos)
            self.userAddChannel(wNick, wChan)
            if '+' in wFlags: self.userSetChannelModes(wNick, wChan, "+v")
            if '%' in wFlags: self.userSetChannelModes(wNick, wChan, "+h")
            if '@' in wFlags: self.userSetChannelModes(wNick, wChan, "+o")
            return

    def process_class4(self, nick, ident, host, remainder):
        self.userAddUpdate(nick, ident, host)
        # NICK
        match = self.regex_class4_nick.match(remainder)
        if match:
            newNick = match.group(1)
            self.userRename(nick, newNick)
            if nick.lower() == self.myNick.lower():
                self.myNick = newNick
                self.log("My new nick is %s" % self.myNick)
            else:
                self.log("%s is now known as %s" % (nick, newNick))
            return
            for modkey in moduleHash:
                moduleHash[modKey].handleNick(nick, newNick)
        # PART
        match = self.regex_class4_part.match(remainder)
        if match:
            partedChan = match.group(1)
            self.userRemoveChannel(nick, partedChan)
            self.log("%s has left %s" % (nick, partedChan))
            for modkey in moduleHash:
                moduleHash[modKey].handlePart(nick, partedChan)
            return
        # QUIT
        match = self.regex_class4_quit.match(remainder)
        if match:
            self.userDelete(nick)
            self.log("%s has quit" % nick)
            for modkey in moduleHash:
                moduleHash[modKey].handleQuit(nick)
            return
        # JOIN
        match = self.regex_class4_join.match(remainder)
        if match:
            joinedChan = match.group(1)
            self.userAddChannel(nick, joinedChan)
            self.log("%s has joined %s" % (nick, joinedChan))
            for modKey in moduleHash:
                moduleHash[modKey].handleJoin(nick, joinedChan)
            return
        # NOTICE
        match = self.regex_class4_notice.match(remainder)
        if match:
            nDest = match.group(1)
            nMsg = match.group(2)
            if nDest.lower() == self.myNick.lower():
                self.log("%s sent me a notice: %s" % (nick, nMsg))
            else:
                self.log("%s sent a notice to %s: %s" % (nick, nDest, nMsg))
            for modKey in moduleHash:
                moduleHash[modKey].handleNotice(nick, nDest, nMsg)
            return
        # PRIVMSG
        match = self.regex_class4_privmsg.match(remainder)
        if match:
            nDest = match.group(1)
            nMsg = match.group(2)
            if nDest.lower() == self.myNick.lower():
                self.log("%s sent me a privmsg: %s" % (nick, nMsg))
            else:
                self.log("%s sent a privmsg to %s: %s" % (nick, nDest, nMsg))
            # Send event to modules
            for modKey in moduleHash:
                moduleHash[modKey].handlePrivmsg(nick, nDest, nMsg)
            return
        # KICK
        match = self.regex_class4_kick.match(remainder)
        if match:
            kChan = match.group(1)
            kVictim = match.group(2)
            kReason = match.group(3)
            self.userRemoveChannel(kVictim, kChan)
            if kVictim.lower() == self.myNick.lower():
                self.log("%s has kicked me out of %s: %s" % (nick, kChan, kReason))
            else:
                self.log("%s has kicked %s out of %s: %s" % (nick, kVictim, kChan, kReason))
            for modKey in moduleHash:
                moduleHash[modKey].handleKick(nick, kChan, kVictim, kReason)
            return
        # MODE
        match = self.regex_class4_mode.match(remainder)
        if match:
            mChan = match.group(1)
            mModes = match.group(2)
            mNicks = None
            if match.group(3):
                mNicks = match.group(3)
                self.log("%s sets modes %s to %s on %s" % (nick, mModes, mNicks, mChan))
                tabNicks = mNicks.split()
                nickIdx = 0
                state = '+'
                for c in mModes:
                    if c in '+-':
                        state = c
                    elif c in 'vhoaq':
                        self.userSetChannelModes(tabNicks[nickIdx], mChan, state + c)
                        nickIdx = nickIdx + 1
                    elif c == 'b':
                        nickIdx = nickIdx + 1 # though it's not a nick
                    #else:
                    #    nickIdx = nickIdx + 1
            else:
                self.log("%s sets modes %s on %s" % (nick, mFlags, mChan))
            for modKey in moduleHash:
                moduleHash[modKey].handleMode(nick, mChan, mModes, mNicks)
            return
        # KILL
        match = self.regex_class4_kill.match(remainder)
        if match:
            kVictim = match.group(1)
            kReason = match.group(2)
            self.userDelete(kVictim)
            self.log("%s has killed %s: %s" % (nick, kVictim, kReason))
            return

    def send(self, msg):
        global mySocket
        if not re.match('^PONG :', msg):
            self.log("S> %s" % msg)
        sendToSocket(msg+"\r\n")

    def say(self, dest, msg):
        self.send("PRIVMSG %s :%s" % (dest, msg))

    def perform(self):
        if self.nickserv_pass != '':
            self.send("PRIVMSG NickServ :IDENTIFY %s" % self.nickserv_pass)
        self.send("MODE %s +x" % self.myNick)
        for c in self.channels:
            self.send("JOIN %s" % c)


##########
## MAIN ##
##########

config = ConfigParser.RawConfigParser()
config.read(execPath + '/pyCrystalBot.cfg')
nick = config.get('main', 'nick')
ident = config.get('main', 'ident')
gecos = config.get('main', 'gecos')
host = config.get('main', 'host')
port = config.getint('main', 'port')
ssl = config.getint('main', 'ssl')
join = config.get('main', 'join')
nickserv_pass = config.get('main', 'nickserv_pass')

log_path = config.get('log', 'path')
logging.basicConfig(filename=log_path, level=logging.DEBUG)

web_host = config.get('web', 'host')
web_port = config.getint('web', 'port')

web=pyCrystalWebServer(web_host, web_port)
bot=pyCrystalBot(nick, ident, gecos, host, port, ssl, join, nickserv_pass)

bot.loadModule('mod01')

web.start()
bot.run()

