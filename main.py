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
import getopt,sys

def usage():
    print "./main.py [OPTIONS]"
    print " -h or --help             This help"
    print " -v or --version          Show version of J2J"
    print " -c file or --config=file Use another configuration file (defaults to: /etc/j2j/j2j.conf)"
    print
    print "See j2j.conf.example for example of configuration file"
    print "See http://wiki.jrudevels.org/J2J for help"

def main():
    __all__=['j2j','client','database','roster','utils','adhoc','debug','config']
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

    try:
        opts, args=getopt.getopt(sys.argv[1:], "c:vo:ho", ["help","config=","version"])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)
    configFile=None
    for o,a in opts:
        if o in ("-v", "--version"):
            print "Jabber-To-Jabber component version:"+version
            sys.exit()
        elif o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-c", "--config"):
            configFile=a
        else:
            assert False, "unhandled option"
    import config
    if configFile:
        config=config.config(configFile)
    else:
        config=config.config()

    c=j2j.j2jComponent(reactor,version,config)
    f=component.componentFactory(config.JID,config.PASSWORD)
    connector = component.buildServiceManager(config.JID, config.PASSWORD, "tcp:%s:%s" % (config.HOST, config.PORT))
    c.setServiceParent(connector)
    connector.startService()
    reactor.run()

if __name__ == "__main__":
    main()