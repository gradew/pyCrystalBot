#!/usr/bin/python2

# self.parentClass.send("PRIVMSG #channel :Hello, world")
# self.parentClass.log("Hi again, my name is %s" % (self.parentClass.myNick))

import re, datetime

logPath = '/opt/pyCrystalBot/log'

class pyCBModule:
    parentClass = None
    logFiles = { }

    def __init__(self, parentClass_):
        self.parentClass = parentClass_

    def logTo(self, logFile_, msg):
        logFile = logFile_.lower()
        logStr="[%s] %s" % (datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"), msg)
        if logFile in self.logFiles:
            fh = self.logFiles[logFile]
        else:
            fh = open("%s/%s.log" % (logPath, logFile), 'w')
            self.logFiles[logFile] = fh
        fh.write("%s\n" % logStr)
        fh.flush()

    def handleNick(self, oldNick, newNick):
        lOldNick = oldNick.lower()
        if lOldNick in self.logFiles:
            lNewNick = newNick.lower()
            fh = self.logFiles[lOldNick]
            fh.close()
            del self.logFiles[lOldNick]
            fh = open("%s/%s.log" % (logPath, lNewNick), 'w')
            self.logFiles[lNewNick] = fh
        else:
            for chan in self.logFiles:
                if re.match('^#', chan):
                    if self.parentClass.isUserInChan(newNick, chan):
                        self.logTo(chan, "%s is now known as %s\n" % (oldNick, newNick))

    def handlePart(self, nick, chan):
        self.logTo(chan, "%s has left %s" % (nick, chan))

    def handleQuit(self, nick):
        for chan in self.logFiles:
            if re.match('^#', chan):
                if self.parentClass.isUserInChan(nick, chan):
                    self.logTo(chan, "%s has quit\n", nick)

    def handleJoin(self, nick, chan):
        self.logTo(chan, "%s has joined %s" % (nick, chan))

    def handleNotice(self, nick, dst, msg):
        lChan = dst.lower()
        if re.match('^#', dst):
            if self.parentClass.isUserInChan(nick, dst):
                self.logTo(dst, "(NOTICE) %s: %s" % (nick, msg))
        else:
            self.logTo(nick, "(NOTICE) %s: %s" % (nick, msg))

    def handlePrivmsg(self, nick, dst, msg):
        lChan = dst.lower()
        if re.match('^#', dst):
            if self.parentClass.isUserInChan(nick, dst):
                self.logTo(dst, "(MSG) %s%s: %s" % (self.parentClass.getUserPrefix(nick, dst), nick, msg))
        else:
            self.logTo(nick, "(MSG) %s: %s" % (nick, msg))

    def handleKick(self, nick, chan, victim, reason):
        self.logTo(chan, "%s has kicked %s out of %s: %s" % (nick, victim, chan, reason))

    def handleMode(self, nick, chan, modes, targets):
        self.logTo(chan, "%s sets modes %s to %s" % (nick, modes, targets))

    def handleClock(self, stime):
        pass
