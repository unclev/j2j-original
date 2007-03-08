import j2j
from twisted.words.protocols.jabber import component
from twisted.internet import reactor
from config import config

__all__=['j2j','client','database','roster','utils','adhoc']
revision=0

__id__="$Id$"
try:
    modRev=int(__id__.split(" ")[2])
except:
    modRev=0

if modRev>revision:
    revision=modRev

for modName in __all__:
    module=__import__(modName,globals(),locals())
    try:
        modRev=int(module.__id__.split(" ")[2])
    except:
        modRev=0
    if modRev>revision:
        revision=modRev

if revision==0:
    revision=''
else:
    revision='.r'+str(revision)

version="1.1.6"+revision

c=j2j.j2jComponent(reactor,"J2J-Twisted version "+version)
f=component.componentFactory(config.JID,config.PASSWORD)
connector = component.buildServiceManager(config.JID, config.PASSWORD, "tcp:%s:%s" % (config.HOST, config.PORT))
c.setServiceParent(connector)
connector.startService()
reactor.run()