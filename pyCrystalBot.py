#!/usr/bin/python2

import socket, time
import os, sys, re, datetime, ConfigParser, pwd
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
moduleLock = threading.Lock()

web_instance = None
bot_instance = None

sys.path.append(execPath + "/modules/")

LOGLEVEL_CRITICAL = 0
LOGLEVEL_ERROR = 1
LOGLEVEL_WARNING = 2
LOGLEVEL_INFO = 3
LOGLEVEL_DEBUG = 4

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

    @app.route('/modload', methods=['POST'])
    def modLoad():
        mName = request.form['name']
        if re.match('^[a-zA-Z0-9\-_\.]+$', mName):
            bot_instance.loadModule(mName)
        return ""

    @app.route('/modunload', methods=['POST'])
    def modUnload():
        mName = request.form['name']
        if re.match('^[a-zA-Z0-9\-_\.]+$', mName):
            bot_instance.unloadModule(mName)
        return ""

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

        # Start clock thread
        tc = threading.Thread(target=self.clockThread)
        tc.daemon = True
        tc.setDaemon(True)
        tc.start()

        while True:
            data = socketFile.readline().strip()
            if data == '':
                continue
            self.process(data)

    def clockThread(self):
        while True:
            time.sleep(10)
            stime = int(time.time())
            moduleLock.acquire()
            for modKey in moduleHash:
                moduleHash[modKey].handleClock(stime)
            moduleLock.release()

    def loadModule(self, name):
        if name in moduleHash:
            self.log("Module %s already loaded" % name, LOGLEVEL_ERROR)
            return False
        fileName = name
        try:
            module = __import__(fileName)
        except:
            self.log("Could not load module %s" % name, LOGLEVEL_ERROR)
            return False
        moduleHash[name] = module.pyCBModule(self)
        self.log("Loaded module %s" % name)
        return True

    def unloadModule(self, name):
        if name not in moduleHash:
            self.log("Module %s was not loaded", LOGLEVEL_ERROR)
            return False
        sys.modules.pop(name)
        del moduleHash[name]
        self.log("Unloaded module %s" % name)
        return True

    def log(self, msg, loglevel=LOGLEVEL_INFO):
        logStr="[%s] %s" % (datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"), msg)
        if loglevel == LOGLEVEL_CRITICAL:
            logging.critical(logStr)
        elif loglevel == LOGLEVEL_ERROR:
            logging.error(logStr)
        elif loglevel == LOGLEVEL_WARNING:
            logging.warning(logStr)
        elif loglevel == LOGLEVEL_INFO:
            logging.info(logStr)
        elif loglevel == LOGLEVEL_DEBUG:
            logging.debug(logStr)

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
        lOldNick = oldNick.lower()
        lNewNick = newNick.lower()
        usersLock.acquire()
        if lOldNick in users:
            userData = users[lOldNick]
            users[lNewNick] = userData
            users[lNewNick]['nick'] = newNick
        usersLock.release()

    def userIsVoice(self, nick, channel):
        res = False
        lNick = nick.lower()
        lChannel = channel.lower()
        usersLock.acquire()
        if lNick in users:
            channels = users[lNick]['channels']
            if lChannel in channels:
                if channels[lChannel]['voice'] == 1:
                    res = True
        usersLock.release()
        return res

    def userIsHalfop(self, nick, channel):
        res = False
        lNick = nick.lower()
        lChannel = channel.lower()
        usersLock.acquire()
        if lNick in users:
            channels = users[lNick]['channels']
            if lChannel in channels:
                if channels[lChannel]['halfop'] == 1:
                    res = True
        usersLock.release()
        return res

    def userIsOp(self, nick, channel):
        res = False
        lNick = nick.lower()
        lChannel = channel.lower()
        usersLock.acquire()
        if lNick in users:
            channels = users[lNick]['channels']
            if lChannel in channels:
                if channels[lChannel]['op'] == 1:
                    res = True
        usersLock.release()
        return res

    def userIsAdmin(self, nick, channel):
        res = False
        lNick = nick.lower()
        lChannel = channel.lower()
        usersLock.acquire()
        if lNick in users:
            channels = users[lNick]['channels']
            if lChannel in channels:
                if channels[lChannel]['admin'] == 1:
                    res = True
        usersLock.release()
        return res

    def userIsOwner(self, nick, channel):
        res = False
        lNick = nick.lower()
        lChannel = channel.lower()
        usersLock.acquire()
        if lNick in users:
            channels = users[lNick]['channels']
            if lChannel in channels:
                if channels[lChannel]['owner'] == 1:
                    res = True
        usersLock.release()
        return res

    def userAddChannel(self, nick, channel):
        lNick = nick.lower()
        lChannel = channel.lower()
        usersLock.acquire()
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
        lNick = nick.lower()
        lChannel = channel.lower()
        usersLock.acquire()
        if lNick in users:
            channels = users[lNick]['channels']
            if lChannel in channels:
                del channels[lChannel]
        usersLock.release()

    def userSetChannelModes(self, nick, chan, modes):
        self.log("userSetChannelModes(%s, %s, %s)" % (nick, chan, modes), LOGLEVEL_DEBUG)
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

        self.log("S< %s" % data, LOGLEVEL_DEBUG)
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
            moduleLock.acquire()
            for modKey in moduleHash:
                moduleHash[modKey].handleNick(nick, newNick)
            moduleLock.release()
            return
        # PART
        match = self.regex_class4_part.match(remainder)
        if match:
            partedChan = match.group(1)
            self.userRemoveChannel(nick, partedChan)
            self.log("%s has left %s" % (nick, partedChan))
            moduleLock.acquire()
            for modKey in moduleHash:
                moduleHash[modKey].handlePart(nick, partedChan)
            moduleLock.release()
            return
        # QUIT
        match = self.regex_class4_quit.match(remainder)
        if match:
            self.userDelete(nick)
            self.log("%s has quit" % nick)
            moduleLock.acquire()
            for modKey in moduleHash:
                moduleHash[modKey].handleQuit(nick)
            moduleLock.release()
            return
        # JOIN
        match = self.regex_class4_join.match(remainder)
        if match:
            joinedChan = match.group(1)
            self.userAddChannel(nick, joinedChan)
            self.log("%s has joined %s" % (nick, joinedChan))
            moduleLock.acquire()
            for modKey in moduleHash:
                moduleHash[modKey].handleJoin(nick, joinedChan)
            moduleLock.release()
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
            moduleLock.acquire()
            for modKey in moduleHash:
                moduleHash[modKey].handleNotice(nick, nDest, nMsg)
            moduleLock.release()
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
            moduleLock.acquire()
            for modKey in moduleHash:
                moduleHash[modKey].handlePrivmsg(nick, nDest, nMsg)
            moduleLock.release()
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
            moduleLock.acquire()
            for modKey in moduleHash:
                moduleHash[modKey].handleKick(nick, kChan, kVictim, kReason)
            moduleLock.release()
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
            else:
                self.log("%s sets modes %s on %s" % (nick, mFlags, mChan))
            moduleLock.acquire()
            for modKey in moduleHash:
                moduleHash[modKey].handleMode(nick, mChan, mModes, mNicks)
            moduleLock.release()
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
            self.log("S> %s" % msg, LOGLEVEL_DEBUG)
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
pid_file = config.get('main', 'pid')
r_user = config.get('main', 'user')
log_path = config.get('log', 'path')
log_level = config.get('log', 'level').lower()

if os.path.isfile(pid_file):
    print("PID file exists!")
    sys.exit(1)

try:
    fl = open(pid_file, 'w')
    fl.close()
except:
    print("Cannot create PID file!")
    sys.exit(1)

try:
    r_uid = pwd.getpwnam(r_user).pw_uid
except:
    print("Specified user or group doesn't exist!")
    sys.exit(1)

if log_level == 'critical':
    logging.basicConfig(filename=log_path, level=logging.CRITICAL)
elif log_level == 'error':
    logging.basicConfig(filename=log_path, level=logging.ERROR)
elif log_level == 'warning':
    logging.basicConfig(filename=log_path, level=logging.WARNING)
elif log_level == 'debug':
    logging.basicConfig(filename=log_path, level=logging.DEBUG)
else:
    logging.basicConfig(filename=log_path, level=logging.INFO)

web_host = config.get('web', 'host')
web_port = config.getint('web', 'port')

web_instance=pyCrystalWebServer(web_host, web_port)
bot_instance=pyCrystalBot(nick, ident, gecos, host, port, ssl, join, nickserv_pass)

newpid = os.fork()
if newpid == 0:
    os.setuid(r_uid)
    web_instance.start()
    bot_instance.run()
else:
    # Write PID
    fl = open(pid_file, 'w')
    fl.write(str(newpid))
    fl.close()

