import j2j
from twisted.words.protocols.jabber import component
from twisted.internet import reactor
from config import config
from twisted.python import versions

version=versions.Version("j2j",1,1,5)

c=j2j.j2jComponent(reactor,version.package+' version '+version.base())
f=component.componentFactory(config.JID,config.PASSWORD)
connector = component.buildServiceManager(config.JID, config.PASSWORD, "tcp:%s:%s" % (config.HOST, config.PORT))
c.setServiceParent(connector)
connector.startService()
reactor.run()