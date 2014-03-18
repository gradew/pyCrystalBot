#!/usr/bin/python2

# self.parentClass.send("PRIVMSG #channel :Hello, world")
# self.parentClass.log("Hi again, my name is %s" % (self.parentClass.myNick))

class pyCBModule:
    parentClass = None
    def __init__(self, parentClass_):
        self.parentClass = parentClass_
        self.parentClass.log("Module mod01 loaded!")

    def handleNick(self, oldNick, newNick):
        pass

    def handlePart(self, nick, chan):
        pass

    def handleQuit(self, nick):
        pass

    def handleJoin(self, nick, chan):
        pass

    def handleNotice(self, nick, dst, msg):
        pass

    def handlePrivmsg(self, nick, dst, msg):
        pass

    def handleKick(self, nick, chan, victim, reason):
        pass

    def handleMode(self, nick, chan, modes, targets):
        pass

