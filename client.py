# Part of J2J (http://JRuDevels.org)
# Copyright 2007 JRuDevels.org

import types
import sys
import utils
import urllib2
from urllib import urlencode
from roster import roster
from twisted.names.error import DNSNameError
from twisted.internet.error import DNSLookupError,TimeoutError,ConnectionDone
from twisted.names.srvconnect import SRVConnector
from twisted.words.xish import domish,xpath
from twisted.words.protocols.jabber import xmlstream, client, jid
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
from twisted.internet import threads,defer,reactor
from twisted.words.protocols.jabber.xmlstream import FeatureNotAdvertized
from twisted.words.protocols.jabber.error import StanzaError
from twisted.words.protocols.jabber.sasl import SASLNoAcceptableMechanism,SASLAuthError,get_mechanisms,sasl_mechanisms
from twisted.words.protocols.jabber.sasl_mechanisms import ISASLMechanism
from twisted.words.protocols.jabber import sasl
from twisted.words.protocols.jabber.client import CheckVersionInitializer,BindInitializer,SessionInitializer
import twisted.words.protocols.jabber.client
from zope.interface import implements
import twisted.web.client

__id__ = "$Id$"

class XMPPAndGoogleAuthenticator(client.XMPPAuthenticator):
    def __init__(self,jid,password,client):
        self.client=client
        twisted.words.protocols.jabber.client.XMPPAuthenticator.__init__(self,jid,password)

    def associateWithStream(self, xs):
        xmlstream.ConnectAuthenticator.associateWithStream(self, xs)

        xs.initializers = [CheckVersionInitializer(xs)]
        inits = [ (xmlstream.TLSInitiatingInitializer, False,False),
                  (SASLAndXGoogleToken, True,True),
                  (BindInitializer, False,False),
                  (SessionInitializer, False,False),
                ]

        for initClass, required, isGoogleClass in inits:
            if not isGoogleClass:
                init = initClass(xs)
            else:
                init = initClass(xs,self.client)
            init.required = required
            xs.initializers.append(init)

class SASLAndXGoogleToken(sasl.SASLInitiatingInitializer):
    def __init__(self,xs,client):
        self.client=client
        sasl.SASLInitiatingInitializer.__init__(self,xs)

    def start(self):
        jid = self.xmlstream.authenticator.jid
        password = self.xmlstream.authenticator.password

        mechanisms = get_mechanisms(self.xmlstream)

        if 'X-GOOGLE-TOKEN' in mechanisms:
            self.mechanism = XGoogleToken(jid.userhost(),password,self)
            self.client.isGTalk=True
        elif 'DIGEST-MD5' in mechanisms:
            self.mechanism = sasl_mechanisms.DigestMD5('xmpp', jid.host, None,
                                                       jid.user, password)
        elif 'PLAIN' in mechanisms:
            self.mechanism = sasl_mechanisms.Plain(None, jid.user, password)
        else:
            return defer.fail(SASLNoAcceptableMechanism)

        self._deferred = defer.Deferred()
        self.xmlstream.addObserver('/challenge', self.onChallenge)
        self.xmlstream.addOnetimeObserver('/success', self.onSuccess)
        self.xmlstream.addOnetimeObserver('/failure', self.onFailure)
        if not self.client.isGTalk:
            self.sendAuth(self.mechanism.getInitialResponse())
        else:
            self.mechanism.getInitialResponse()
        return self._deferred

class XGoogleToken(object):
    implements(ISASLMechanism)
    name='X-GOOGLE-TOKEN'
    def __init__(self,login,password,host):
        self.login=login
        self.password=password
        self.host=host

    def getInitialResponse(self):
        lib=urlencode({"Email": self.login, "Passwd": self.password, "PersistentCookie": "false", "source": "googletalk", "accountType": "HOSTED_OR_GOOGLE"})
        defr=twisted.web.client.getPage("https://google.com/accounts/ClientAuth",method="POST",postdata=lib,headers={"Content-Type": "application/x-www-form-urlencoded"})
        defr.addCallback(self.firstDefer)
        defr.addErrback(self.firstDefer)
        return

    def firstDefer(self,respond):
        try:
            if respond.find("Error")==0:
                return self.secondDefer("Error")
        except:
                return self.secondDefer("Error")

        pars=respond.split("\n")
        SID=pars[0]
        LSID=pars[1]

        lib=urlencode({"SID": SID[4:], "LSID": LSID[5:], "service": "mail", "Session": "true"})

        defr=twisted.web.client.getPage("https://google.com/accounts/IssueAuthToken",method="POST",postdata=lib,headers={"Content-Type": "application/x-www-form-urlencoded"})
        defr.addCallback(self.secondDefer)
        defr.addErrback(self.secondDefer)
        return

    def secondDefer(self,respond):
        try:
            self.host.sendAuth("\x00%s\x00%s" % (self.login,respond.splitlines()[0]))
        except:
            self.host.sendAuth("\x00")

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
        self.host.component.debug.loginsLog("User %s has error in connection:\n%s" % (self.host.host_jid.full(),str(reason)))
        error="remote-server-not-found"
        cond="cancel"
        if reason.check(DNSNameError,DNSLookupError) and self.host.tryingSRV:
            self.stopTrying()
            self.host.tryingSRV=False
            self.host.reactor.connectTCP(self.host.server,self.host.port,self.host.f)
            return
        elif reason.check(DNSNameError,DNSLookupError) and not self.host.tryingSRV:
            self.stopTrying()
        elif reason.check(TimeoutError):
            error="remote-server-timeout"
            cond="wait"
        self.host.component.sendPresenceError(self.host.host_jid.full(),self.host.config.JID,cond,error)
        self.host.component.deleteClient(self.host.host_jid)

    def clientConnectionLost(self, connector, reason):
        self.host.component.debug.loginsLog("User %s has lost connection\n%s" % (self.host.host_jid.full(),str(reason)))

class Client(object):
    def __init__(self, el, reactor, component, host_jid, client_jid, server, secret, port=5222,import_roster=False,remove_from_roster=False):
        self.config=component.config
        self.xmlstream=None
        self.isGTalk=False
        self.presences = {}
        self.presences_available = []
        self.presences_available_full = []
        self.alreadyReply = []
        self.component=component
        self.connected=False
        self.authenticated=False
        self.host_jid=host_jid
        self.roster=roster(self)
        self.reactor=reactor
        self.server=server
        self.port=port
        self.import_roster=import_roster
        self.remove_from_roster=remove_from_roster
        self.client_jid=client_jid
        self.disconnect=False
        self.error=False
        self.secret=secret
        self.mail_time=0
        self.mail_tid=0
        self.presenceSent=False
        a = XMPPAndGoogleAuthenticator(client_jid, secret, self)
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
        self.component.debug.loginsLog("User %s is connecting to %s:%s with guest-jid %s" % (host_jid.full(),server,str(port),client_jid.full()))
        self.connector.connect()
        #reactor.connectTCP(server,port,self.f)

    def onConnected(self, xs):
        self.xmlstream = xs
        self.xmlstream.rawDataInFn=self.rawIn
        self.xmlstream.rawDataOutFn=self.rawOut
        if not self.disconnect:
            self.connected = True
        else:
            self.xmlstream.sendFooter()

    def rawIn(self,data):
        self.component.debug.clientsXmlsLog(data,self.client_jid,self.host_jid)

    def rawOut(self,data):
        self.component.debug.clientsXmlsLog(data,self.client_jid,self.host_jid,True)

    def onDisconnected(self, xs):
        if self.tryingNonSASL and not self.connected: return
        self.f.stopTrying()
        if not self.error:
            presence=Element((None,'presence'))
            presence.attributes['to']=self.host_jid.full()
            presence.attributes['from']=self.config.JID
            presence.attributes['type']='unavailable'
            presence.addElement('status',content="Disconnected")
            self.component.send(presence)
        uid=self.component.db.getIdByJid(self.host_jid.userhost())
        if (self.presences_available_full!=[] or self.presences!={}) and uid:
            unPres=Element((None,"presence"))
            unPres.attributes["to"]=self.host_jid.full()
            unPres.attributes["type"]="unavailable"
            for ojid in self.presences_available_full:
                unPres.attributes["from"]=utils.quoteJID(ojid,self.config.JID)
                self.component.send(unPres)
            for ojid in self.presences.keys():
                if self.component.db.getCount('rosters',"id='%s' AND jid='%s'" % (str(uid),ojid.split("/")[0].encode('utf-8'))):
                    unPres.attributes["from"]=utils.quoteJID(ojid,self.config.JID)
                    self.component.send(unPres)
        self.component.deleteClient(self.host_jid)

    def onAuthenticated(self, xs):
        if self.disconnect:
            xs.sendFooter()
            return

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

        self.authenticated=True

        if self.isGTalk:
            self.initGTalk()

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
        if el.attributes.has_key("id"):
            iqId=el.attributes["id"]
        else:
            iqId=None
        if el.attributes.has_key("type"):
            iqType=el.attributes["type"]
        else:
            iqType=None
        if iqId in self.component.adhoc.vCardSids.keys() and iqType=="result":
            if self.component.adhoc.vCardSids[iqId][0].full()==self.host_jid.full():
                iq=Element((None,"iq"))
                iq.attributes["to"]=self.component.adhoc.vCardSids[iqId][0].full()
                iq.attributes["from"]=self.config.JID
                iq.attributes["id"]=self.component.adhoc.vCardSids[iqId][1]
                iq.attributes["type"]="result"
                command=utils.createCommand(iq,"replicate_vCard","completed",iqId)
                self.component.send(iq)
                del self.component.adhoc.vCardSids[iqId]
                return
        for query in el.elements():
            if query.uri=="jabber:iq:roster":
                return
            if query.uri=="google:mail:notify" and query.name=="mailbox":
                self.mailbox(el)
                return
            if query.uri=="google:mail:notify" and query.name=="new-mail":
                self.newmail(el)
                return
        nodes=xpath.XPathQuery('/iq/query[@xmlns="http://jabber.org/protocol/disco#items"]/item').queryForNodes(el)
        if nodes:
            for node in nodes:
                if node.attributes.has_key("jid"):
                    node.attributes["jid"]=utils.quoteJID(node.attributes["jid"],self.config.JID)
        if xpath.XPathQuery('/iq/query[@xmlns="jabber:iq:gateway"]/jid').matches(el):
            nodes=xpath.XPathQuery('/iq[@type="result"]/query[@xmlns="jabber:iq:gateway"]').queryForNodes(el)
            if nodes:
                for node in nodes:
                    ujid=''
                    for jnode in node.elements():
                        if jnode.name=="jid": ujid=unicode(jnode)
                    node.children=[]
                    node.addElement("jid",content=utils.quoteJID(ujid,self.config.JID))

        self.route(el)

    def newmail(self,el):
        iq=Element((None,"iq"))
        iq.attributes["type"]="get"
        q=iq.addElement("query")
        q.attributes["xmlns"]="google:mail:notify"
        q.attributes["q"]="(!label:^s) (!label:^k) ((label:^u) (label:^i) (!label:^vm))"
        q.attributes["newer-than-time"]=str(self.mail_time)
        q.attributes["newer-than-tid"]=str(self.mail_tid)
        self.send(iq)

    def mailbox(self,el):
        total=0
        firstTime=False
        myuid=self.component.db.getIdByJid(self.host_jid.userhost())
        if not myuid:
            return
        options=self.component.db.getOptsById(myuid)
        if self.mail_time==0:
            firstTime=True
        msgs=[]
        for mailbox in el.elements():
            if mailbox.name=="mailbox" and mailbox.uri=="google:mail:notify":
                self.mail_time=mailbox.getAttribute("result-time")
                a=[]
                alTid=False
                for thread in mailbox.elements():
                    if not alTid:
                        self.mail_tid=thread.getAttribute("tid")
                        alTid=True
                    url=thread.getAttribute("url")
                    date=thread.getAttribute("date")
                    senders="\n"
                    subject="Subject: no subject\n"
                    snippet="\n"
                    for elms in thread.elements():
                        if elms.name=="senders":
                            for sender in elms.elements():
                                nameOfSender=sender.getAttribute("name","")
                                addressOfSender=sender.getAttribute("address","")
                                if addressOfSender!='':
                                    addressOfSender=" <%s> \n" % addressOfSender
                                senders=senders+nameOfSender+addressOfSender
                        if elms.name=="subject":
                            subject="Subject: %s\n" % unicode(elms)
                        if elms.name=="snippet":
                            snippet=unicode(elms)
                    total+=1
                    msgs.append([senders,snippet,date,subject,url])

                if not (firstTime and options[1]):
                    msgs.reverse()
                    for a in msgs:
                        msg=Element((None,"message"))
                        msg.attributes["from"]=self.config.JID
                        msg.attributes["to"]=self.host_jid.full()
                        msg.attributes["type"]="headline"
                        msg.addElement("subject",content="Google New Mail Notify")
                        msg.addElement("body",content="From: %s\n%s" % (a[0],a[1]))
                        x=msg.addElement((None,"x"))
                        x.attributes["xmlns"]="jabber:x:oob"
                        try:
                            x.addElement("desc",content=subject+' '+time.strftime("%a %d %b %Y, %H:%M",time.gmtime(long(a[2]))))
                        except:
                            x.addElement("desc",content=a[3])
                        x.addElement("url",content=a[4])
                        self.component.send(msg)

            if firstTime and options[1] and total>0:
                msg=Element((None,"message"))
                msg.attributes["from"]=self.config.JID
                msg.attributes["to"]=self.host_jid.full()
                msg.attributes["type"]="headline"
                msg.addElement("subject",content="Google New Mail Notify")
                msg.addElement("body",content="You have %s unread letters." % (str(total)))
                x=msg.addElement((None,"x"))
                x.attributes["xmlns"]="jabber:x:oob"
                x.addElement("desc",content="You have %s unread letters." % (str(total)))
                x.addElement("url",content=url)
                self.component.send(msg)

    def route(self,el):
        fro = el.getAttribute("from")
        to = el.getAttribute("to")
        try:
            fro=internJID(fro)
            to=internJID(to)
        except:
            return
        el.attributes["from"]=utils.quoteJID(fro.full(),self.config.JID)
        if to.full()==to.userhost():
            el.attributes["to"]=self.host_jid.userhost()
        else:
            el.attributes["to"]=self.host_jid.full()
        utils.delUri(el)
        uid=self.component.db.getIdByJid(self.host_jid.userhost())
        if not uid: return
        opts=self.component.db.getOptsById(uid)
        if opts[3] and (el.name=="message" or el.name=="iq"):
            if not (fro.userhost() in self.roster.items.keys()):
                return
        if opts[4]:
            flag=False
            if el.name=="message" and el.getAttribute("type")!="groupchat" and el.getAttribute("type")!="headline": flag=True
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
        self.component.debug.loginsLog("User %s has fail in connection init:\n%s" % (self.host_jid.full(),str(failure)))
        if failure.check(ConnectionDone):
            self.xmlstream.sendFooter()
            return

        if failure.check(StanzaError,SASLNoAcceptableMechanism,SASLAuthError):
            self.error=True
            self.component.sendPresenceError(self.host_jid.full(),self.config.JID,"auth",'not-authorized')
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

    def initGTalk(self):
        iq=Element((None,"iq"))
        iq.attributes["type"]="set"
        q=iq.addElement("usersetting")
        q.attributes["xmlns"]="google:setting"
        x=q.addElement("autoacceptrequests")
        x.attributes["value"]="false"
        y=q.addElement("mailnotifications")
        y.attributes["value"]="true"
        self.send(iq)
        iq=Element((None,"iq"))
        iq.attributes["type"]="get"
        iq.attributes["id"]="getGoogleMail"
        q=iq.addElement("query")
        q.attributes["xmlns"]="google:mail:notify"
        q.attributes["q"]="(!label:^s) (!label:^k) ((label:^u) (label:^i) (!label:^vm))"
        self.send(iq)
