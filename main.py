#!/usr/bin/python
# J2J - Jabber-To-Jabber component
# http://JRuDevels.org
# http://wiki.JRuDevels.org
#
# copyright 2007 Dobrov Sergey aka Binary from JRuDevels
#
# License: GPL-v3
#

import j2j
from twisted.words.protocols.jabber import component
from twisted.internet import reactor
from twisted.scripts import _twistd_unix as twistd
import getopt
import os
import sys
from config import Config


def main():
    __all__=['j2j','client','database','roster',
             'utils','adhoc','debug','config']
    revision=0
    date=0

    __id__="$Id$"

    try:
        modRev=int(__id__.split(" ")[2])
        modDate=int(__id__.split(" ")[3].replace("-",""))
    except:
        modRev=0
        modDate=0

    if modRev>revision:
        revision=modRev
    if modDate>date:
        date=modDate

    for modName in __all__:
        module=__import__(modName,globals(),locals())
        try:
            modRev=int(module.__id__.split(" ")[2])
            modDate=int(module.__id__.split(" ")[3].replace("-",""))
        except:
            modRev=0
            modDate=0
        if modRev>revision:
            revision=modRev
        if modDate>date:
            date=modDate

    if revision==0:
        revision=''
    else:
        revision='.r'+str(revision)
    if date!=0:
        date=str(date)
        revision=revision+" %s-%s-%s" % (date[:4],date[4:6],date[6:8])

    version="1.1.8"+revision

    from optparse import OptionParser
    parser = OptionParser(version=
                          "Jabber-To-Jabber component version:"+version)
    parser.add_option('-c','--config', metavar='FILE', dest='configFile',
                      help="Read config from custom file")
    parser.add_option('-b','--background', dest='configBackground',
                      help="Daemonize/background transport",
                      action="store_true")
    (options,args) = parser.parse_args()
    configFile = options.configFile
    configBackground = options.configBackground

    if configFile:
        config=Config(configFile)
    else:
        config=Config()
    if configBackground and os.name == "posix": # daemons supported?
        twistd.daemonize() # send to background
    if config.PROCESS_PID:
        pid = str(os.getpid())
        pidfile = open(config.PROCESS_PID, "w")
        pidfile.write("%s\n" % pid)
        pidfile.close()

    c=j2j.j2jComponent(reactor,version,config)
    f=component.componentFactory(config.JID,config.PASSWORD)
    connector = component.buildServiceManager(config.JID, config.PASSWORD,
                                     "tcp:%s:%s" % (config.HOST, config.PORT))
    c.setServiceParent(connector)
    connector.startService()
    reactor.run()

if __name__ == "__main__":
    main()