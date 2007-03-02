import types
import sys
import utils
from config import config
from roster import roster
from twisted.names.error import DNSNameError
from twisted.internet.error import DNSLookupError,TimeoutError,ConnectionDone
from twisted.names.srvconnect import SRVConnector
from twisted.words.xish import domish,xpath
from twisted.words.protocols.jabber import xmlstream, client, jid
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
from twisted.internet import threads
from twisted.words.protocols.jabber.xmlstream import FeatureNotAdvertized
from twisted.words.protocols.jabber.error import StanzaError
from twisted.words.protocols.jabber.sasl import SASLNoAcceptableMechanism,SASLAuthError

class XMPPClientConnector(SRVConnector):
    def __init__(self, reactor, domain, factory, port=5222):
        self.port=port
        SRVConnector.__init__(self, reactor, 'xmpp-client', domain, factory)

class ClientFactory(xmlstream.XmlStreamFactory):
    def __init__(self,a,host):
        self.host=host
        xmlstream.XmlStreamFactory.__init__(self,a)
        self.maxRetries=1

    def clientConnectionFailed(self, connector, reason):
        error="remote-server-not-found"
        if reason.check(DNSNameError,DNSLookupError) and self.host.tryingSRV:
            self.stopTrying()
            self.host.tryingSRV=False
            self.host.reactor.connectTCP(self.host.server,self.host.port,self.host.f)
            return
        elif reason.check(DNSNameError,DNSLookupError) and not self.host.tryingSRV:
            self.stopTrying()
        elif reason.check(TimeoutError):
            error="remote-server-timeout"
        self.host.component.sendPresenceError(self.host.host_jid.full(),config.JID,"cancel",error)
        self.host.component.deleteClient(self.host.host_jid)

    def clientConnectionLost(self, connector, reason):
        pass

class Client(object):
    def __init__(self, el, reactor, component, host_jid, client_jid, server, secret, port=5222):
        self.presences = {}
        self.presences_available = []
        self.presences_available_full = []
        self.alreadyReply = []
        self.component=component
        self.connected=False
        self.host_jid=host_jid
        self.roster=roster(self)
        self.reactor=reactor
        self.server=server
        self.port=port
        self.client_jid=client_jid
        self.disconnect=False
        self.error=False
        self.secret=secret
        a = client.XMPPAuthenticator(client_jid, secret)
        self.f = ClientFactory(a,self)
        self.f.addBootstrap(xmlstream.STREAM_CONNECTED_EVENT, self.onConnected)
        self.f.addBootstrap(xmlstream.STREAM_END_EVENT, self.onDisconnected)
        self.f.addBootstrap(xmlstream.STREAM_AUTHD_EVENT, self.onAuthenticated)
        self.f.addBootstrap(xmlstream.INIT_FAILED_EVENT, self.onInitFailed)
        self.startPresence=el
        self.tryingSRV = True
        self.tryingNonSASL = False
        self.tryingSASL = True
        self.connector = XMPPClientConnector(reactor, server, self.f, port)
        self.connector.connect()
        #reactor.connectTCP(server,port,self.f)

    def onConnected(self, xs):
        self.xmlstream = xs
        if not self.disconnect:
            self.connected = True
        else:
            self.xmlstream.sendFooter()

    def onDisconnected(self, xs):
        if self.tryingNonSASL and not self.connected: return
        self.f.stopTrying()
        if not self.error:
            presence=Element((None,'presence'))
            presence.attributes['to']=self.host_jid.full()
            presence.attributes['from']=config.JID
            presence.attributes['type']='unavailable'
            presence.addElement('status',content="Disconnected")
            self.component.send(presence)
        uid=self.component.db.getIdByJid(self.host_jid.userhost())
        if (self.presences_available_full!=[] or self.presences!={}) and uid:
            unPres=Element((None,"presence"))
            unPres.attributes["to"]=self.host_jid.full()
            unPres.attributes["type"]="unavailable"
            for ojid in self.presences_available_full:
                unPres.attributes["from"]=utils.quoteJID(ojid)
                self.component.send(unPres)
            for ojid in self.presences.keys():
                if self.component.db.getCount('rosters',"id='%s' AND jid='%s'" % (str(uid),ojid.split("/")[0].encode('utf-8'))):
                    unPres.attributes["from"]=utils.quoteJID(ojid)
                    self.component.send(unPres)
        self.component.deleteClient(self.host_jid)

    def onAuthenticated(self, xs):
        if self.disconnect:
            xs.sendFooter()
            return

        presence=Element((None,'presence'))
        presence.attributes['to']=self.host_jid.full()
        presence.attributes['from']=config.JID
        presence.addElement('status',content="Online")
        self.component.send(presence)

        self.xmlstream.addObserver("/iq/query[@xmlns='jabber:iq:roster']",self.roster.onIq)
        self.xmlstream.addObserver("/message",self.onMessage)
        self.xmlstream.addObserver("/presence",self.onPresence)
        self.xmlstream.addObserver("/iq",self.onIq)


        self.startPresence.attributes={}

        if self.startPresence.attributes.has_key("xmlns"):
            del self.startPresence["xmlns"]

        xs.send(self.startPresence)
        del self.startPresence

        rosterReq=Element((None,'iq'))
        rosterReq.attributes['type']='get'
        rosterReq.attributes['id']='getRoster'
        rosterQ=rosterReq.addElement('query')
        rosterQ.attributes['xmlns']='jabber:iq:roster'
        xs.send(rosterReq)

    def onMessage(self,el):
        self.route(el)

    def onPresence(self,el):
        fro = el.getAttribute("from")
        to = el.getAttribute("to")
        presType = el.getAttribute("type")
        try:
            fro=internJID(fro)
            to=internJID(to)
        except:
            return
        uid=self.component.db.getIdByJid(self.host_jid.userhost())
        if not uid: return
        isInRoster=self.component.db.getCount("rosters","id='%s' AND jid='%s'" % (str(uid),self.component.db.dbQuote(fro.userhost().encode('utf-8'))))
        if presType=="available" or presType==None:
            self.presences[fro.full()]=el
            if isInRoster==0 and (not fro.userhost() in self.presences_available):
                return
        elif presType=="unavailable":
            if self.presences.has_key(fro.full()):
                del self.presences[fro.full()]
            if isInRoster==0 and (not fro.userhost() in self.presences_available):
                return
        elif presType=="error":
            if isInRoster==0 and (not fro.userhost() in self.presences_available):
                return
        self.route(el)

    def onIq(self,el):
        for query in el.elements():
            if query.uri=="jabber:iq:roster":
                return
        nodes=xpath.XPathQuery('/iq/query[@xmlns="http://jabber.org/protocol/disco#items"]/item').queryForNodes(el)
        if nodes:
            for node in nodes:
                if node.attributes.has_key("jid"):
                    node.attributes["jid"]=utils.quoteJID(node.attributes["jid"])
        if xpath.XPathQuery('/iq/query[@xmlns="jabber:iq:gateway"]/jid').matches(el):
            nodes=xpath.XPathQuery('/iq[@type="result"]/query[@xmlns="jabber:iq:gateway"]').queryForNodes(el)
            if nodes:
                for node in nodes:
                    ujid=''
                    for jnode in node.elements():
                        if jnode.name=="jid": ujid=unicode(jnode)
                    node.children=[]
                    node.addElement("jid",content=utils.quoteJID(ujid))

        self.route(el)

    def route(self,el):
        fro = el.getAttribute("from")
        to = el.getAttribute("to")
        try:
            fro=internJID(fro)
            to=internJID(to)
        except:
            return
        el.attributes["from"]=utils.quoteJID(fro.full())
        el.attributes["to"]=self.host_jid.full()
        if el.attributes.has_key("xmlns"):
            del el.attributes["xmlns"]
        uid=self.component.db.getIdByJid(self.host_jid.userhost())
        if not uid: return
        opts=self.component.db.getOptsById(uid)
        if opts[3] and (el.name=="message" or el.name=="iq"):
            if not (fro.userhost() in self.roster.items.keys()):
                return
        if opts[4]:
            flag=False
            if el.name=="message": flag=True
            if el.name=="subscribe" and el.getAttribute("type")=="subscribe":
                flag=True
                pres=Element((None,"presence"))
                pres.attributes["to"]=fro.userhost()
                pres.attributes["type"]="unsubscribed"
                self.send(pres)
            if (not fro.full() in self.alreadyReply) and flag:
                msg=Element((None,"message"))
                msg.attributes["to"]=fro.full()
                msg.attributes["type"]="normal"
                msg.addElement("subject",content="J2J Auto Reply Service")
                msg.addElement("body",content=opts[0])
                self.send(msg)
                self.alreadyReply.append(fro.full())
            if not opts[2]:
                return
        self.component.send(el)

    def send(self, el):
        if not self.xmlstream: return False
        self.xmlstream.send(el)
        return True

    def onInitFailed(self, failure):
        if failure.check(ConnectionDone):
            self.xmlstream.sendFooter()
            return

        if failure.check(StanzaError,SASLNoAcceptableMechanism,SASLAuthError):
            self.error=True
            self.component.sendPresenceError(self.host_jid.full(),config.JID,"cancel",'not-authorized')
            self.onDisconnected(None)
            return

        if failure.check(FeatureNotAdvertized) and self.tryingSASL:
            self.tryingSASL = False
            self.tryingSRV = True
            self.tryingNonSASL = True
            a = client.BasicAuthenticator(self.client_jid, self.secret)
            xmlstream.XmlStreamFactory(a)
            self.f = ClientFactory(a,self)
            self.f.addBootstrap(xmlstream.STREAM_CONNECTED_EVENT, self.onConnected)
            self.f.addBootstrap(xmlstream.STREAM_END_EVENT, self.onDisconnected)
            self.f.addBootstrap(xmlstream.STREAM_AUTHD_EVENT, self.onAuthenticated)
            self.f.addBootstrap(xmlstream.INIT_FAILED_EVENT, self.onInitFailed)
            self.connector = XMPPClientConnector(self.reactor, self.server, self.f, self.port)
            self.connector.connect()
            return
        self.xmlstream.sendFooter()