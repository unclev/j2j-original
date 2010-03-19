import time

__id__ = "$Id$"

class Debug:
    def __init__(self, logFile, registrations, logins, xmlLogFile,
                 componentXmlLog, clientsXmlLog, clientJidsToLog):
        self.logFile = logFile
        self.registrations = registrations
        self.logins = logins
        self.xmlLogFile = xmlLogFile
        self.componentXmlLog = componentXmlLog
        self.clientsXmlLog = clientsXmlLog
        self.clientJidsToLog = clientJidsToLog
        self.clAcl = clientJidsToLog.split(",")

    def getTheTime(self):
        return time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(time.time()))

    def registrationsLog(self, message):
        if self.registrations:
            lf = open(self.logFile, "ab")
            s = "==Registration message== on %s\n%s\n\n" % \
                (self.getTheTime(), message)
            lf.write(s.encode("utf-8"))
            lf.close()

    def loginsLog(self, message):
        if self.logins:
            lf = open(self.logFile, "ab")
            s = "==Login message== on %s\n%s\n\n" % \
                (self.getTheTime(), message)
            lf.write(s.encode("utf-8"))
            lf.close()

    def componentXmlsLog(self, data, out=False):
        if self.componentXmlLog:
            xlf = open(self.xmlLogFile, "ab")
            if out:
                s = ">>> Component on %s\n%s\n" % (self.getTheTime() ,data)
            else:
                s = "<<< Component on %s\n%s\n" % (self.getTheTime(), data)
            xlf.write(s)
            xlf.close()

    def clientsXmlsLog(self, data, jid, hjid, out=False):
        if self.clientsXmlLog and \
           (hjid.userhost() in self.clAcl or self.clAcl==["All"]):
            xlf = open(self.xmlLogFile,"ab")
            if out:
                s = ">>> Client %s, host %s on %s\n%s\n" % \
                    (jid.full(), hjid.full(), self.getTheTime(), data)
            else:
                s = "<<< Client %s, host %s on %s\n%s\n" % \
                    (jid.full(), hjid.full(), self.getTheTime(), data)
            xlf.write(s)
            xlf.close()
