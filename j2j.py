import md5
from config import config
from client import Client
from adhoc import adHoc
import time
import os
import sys
import codecs #!
import utils
import database
from twisted.internet import reactor
from twisted.words.xish import domish,xpath
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber import xmlstream, client, jid, component
from twisted.words.protocols.jabber.jid import internJID

reload(sys)
sys.setdefaultencoding("utf-8")
sys.stdout = codecs.lookup('utf-8')[-1](sys.stdout)

class j2jComponent(component.Service):
    VERSION="0.1.2"

    def __init__(self,reactor):
        self.reactor=reactor
        self.adhoc=adHoc(self)

    def componentConnected(self, xs):
        self.startTime = time.time()
        self.clients = {}
        self.db=database.database()
        self.xmlstream = xs
        self.xmlstream.addObserver("/iq", self.onIq)
        self.xmlstream.addObserver("/presence", self.onPresence)
        self.xmlstream.addObserver("/message", self.onMessage)
        print "Connected"

    def onMessage(self,el):
        fro = el.getAttribute("from")
        to = el.getAttribute("to")
        try:
            fro=internJID(fro)
            to=internJID(to)
        except:
            return
        if to.full()==config.JID: return
        self.routeStanza(el,fro,to)

    def routeStanza(self, el, fro, to):
        froStr=fro.full()
        if fro.full()==fro.userhost():
            f=False
            for cl in self.clients.keys():
                if cl.find(froStr+"/")==0:
                    f=True
                    froStr=cl
            if not f:
                return
        elif not self.clients.has_key(fro.full()):
            return

        el.attributes['to'] = utils.unquoteJID(to.full())
        del el.attributes['from']
        if el.attributes.has_key("xmlns"):
            del el.attributes['xmlns']
        del el.uri
        del el.defaultUri

        self.clients[froStr].send(el)

    def onPresence(self, el):
        fro = el.getAttribute("from")
        to = el.getAttribute("to")
        presenceType = el.getAttribute("type")
        try:
            fro=internJID(fro)
            to=internJID(to)
        except:
            return

        if to.full()==config.JID:
            self.componentPresence(el,fro,presenceType)
            return

        uid=self.db.getIdByJid(fro.userhost())
        if not uid:
            return

        if presenceType=="available" or presenceType==None:
            froStr=fro.full()
            if not self.clients.has_key(fro.full()): return
            if not utils.unquoteJID(to.userhost()) in self.clients[froStr].presences_available:
                self.clients[froStr].presences_available.append(utils.unquoteJID(to.userhost()))
            if not utils.unquoteJID(to.full()) in self.clients[froStr].presences_available_full:
                self.clients[froStr].presences_available_full.append(utils.unquoteJID(to.full()))

        if presenceType=="subscribe":
            froStr=fro.userhost()
            toUnq=utils.unquoteJID(to.userhost())
            f=False
            for cl in self.clients.keys():
                if cl.find(froStr+"/")==0:
                    f=True
                    froStr=cl
            if not f:
                return
            if self.clients[froStr].roster.items.has_key(toUnq):
                if not self.db.getCount('rosters',"id='%s' AND jid='%s'" % (str(uid),toUnq.encode("utf-8"))):
                    self.db.execute("INSERT INTO %s (id,jid) VALUES ('%s','%s')" % (self.db.dbTablePrefix+"rosters", str(uid), self.db.dbQuote(toUnq.encode("utf-8"))))
                    self.db.commit()
                subscription=self.clients[froStr].roster.items[toUnq][1]
                if subscription in ["both","to"]:
                    p = Element((None,"presence"))
                    p.attributes["to"]=fro.userhost()
                    p.attributes["from"]=to.userhost()
                    p.attributes["type"]="subscribed"
                    self.send(p)
                    if subscription=="both":
                        p.attributes["type"]="subscribe"
                        self.send(p)

                    for pr in self.clients[cl].presences.keys():
                        if pr.split('/')[0]==toUnq:
                            pres=self.clients[froStr].presences[pr]
                            pres.attributes["from"]=utils.quoteJID(pr)
                            pres.attributes["to"]=fro.full()
                            pres.uri=None
                            pres.defaultUri=None
                            self.send(pres)
                    return

        if presenceType=="unsubscribe":
            toUnq=utils.unquoteJID(to.full())
            if self.db.getCount('rosters',"id='%s' AND jid='%s'" % (str(uid),toUnq.encode("utf-8"))):
                self.db.execute("DELETE FROM %s WHERE id='%s' AND jid='%s'" % (self.db.dbTablePrefix+"rosters", str(uid), self.db.dbQuote(toUnq.encode('utf-8'))))
                self.db.commit()
                p = Element((None,'presence'))
                p.attributes["to"]=fro.userhost()
                p.attributes["from"]=to.userhost()
                p.attributes["type"]="unsubscribed"
                self.send(p)
                return

        self.routeStanza(el,fro,to)

    def componentPresence(self,el,fro,presenceType):
        uid=self.db.getIdByJid(fro.userhost())
        if not uid:
            self.sendPresenceError(to=fro.full(),fro=config.JID,etype="cancel",condition="registration-required")
            return
        data=self.db.getDataById(uid)
        resource=jid.parse(fro.full())[2]
        if resource==None:
            resource=''
        else:
            resource="/"+resource
        clientJid=jid.JID(data[0]+"@"+data[2]+resource)
        if data[3]==None or data[3]=='':
            data[3]=data[2]
        newjid=(data[0]+"@"+data[2]).encode('utf-8')
        newmd5=md5.md5(newjid).hexdigest()
        if not self.clients.has_key(fro.full()) and (presenceType=="available" or presenceType==None):
            js=[]
            for element in el.elements():
                if element.name=="x" and element.uri=="j2j:history":
                    try:
                        hops=int(element.attributes["hops"])
                    except:
                        hops=0
                    if hops>3:
                        self.sendPresenceError(fro.full(),config.JID,"cancel","not-allowed")
                        return
                    element.attributes["hops"]=str(hops+1)
                    for jidmd5 in element.elements():
                        if jidmd5.name=="jid":
                            js.append(unicode(jidmd5))
                    element.addElement("jid",content=md5.md5(fro.full().encode("utf-8")).hexdigest())
            if newmd5 in js:
                self.sendPresenceError(fro.full(),config.JID,"cancel","conflict")
                return
            if js==[]:
                j2jh=el.addElement("x")
                j2jh.uri="j2j:history"
                j2jh.defaultUri="j2j:history"
                j2jh.attributes["hops"]="1"
                j2jh.addElement("jid",content=md5.md5(fro.full().encode("utf-8")).hexdigest())
            del el.uri
            del el.defaultUri
            presence=Element((None,'presence'))
            presence.attributes['to']=fro.full()
            presence.attributes['from']=config.JID
            presence.addElement('show',content="xa")
            presence.addElement('status',content="Logging in...")
            self.send(presence)
            self.clients[fro.full()]=Client(el,self.reactor,self,fro,clientJid,data[3],data[1],data[4])
        elif self.clients.has_key(fro.full()) and presenceType=="unavailable":
            if self.clients[fro.full()].connected:
                self.clients[fro.full()].xmlstream.sendFooter()
            else:
                self.disconnect=True
        elif self.clients.has_key(fro.full()) and (presenceType=="available" or presenceType==None):
            if self.clients[fro.full()].connected:
                del el.attributes["to"]
                del el.attributes["from"]
                del el.uri
                del el.defaultUri
                self.clients[fro.full()].send(el)
        elif presenceType=="subscribe":
            presence=Element((None,'presence'))
            presence.attributes['to']=fro.full()
            presence.attributes['from']=config.JID
            presence.attributes['type']='subscribed'
            self.send(presence)

    def deleteClient(self,jid):
        del self.clients[jid.full()]

    def onIq(self, el):
        fro = el.getAttribute("from")
        to = el.getAttribute("to")
        ID = el.getAttribute("id")
        iqType = el.getAttribute("type")
        try:
            fro=internJID(fro)
            to=internJID(to)
        except Exception, e:
            return
        if to.full()==config.JID:
            self.componentIq(el,fro,ID,iqType)
            return
        self.routeStanza(el,fro,to)

    def componentIq(self,el,fro,ID,iqType):
        for query in el.elements():
            xmlns=query.uri
            node=query.getAttribute("node")

            if xmlns=="jabber:iq:register" and iqType=="get":
                self.getRegister(el,fro,ID)
                return

            if xmlns=="jabber:iq:register" and iqType=="set":
                self.setRegister(el,fro,ID)
                return

            if xmlns=="http://jabber.org/protocol/disco#info" and iqType=="get":
                self.getDiscoInfo(el,fro,ID,node)
                return

            if xmlns=="http://jabber.org/protocol/disco#items" and iqType=="get":
                self.getDiscoItems(el,fro,ID,node)
                return

            if xmlns=="jabber:iq:last" and iqType=="get":
                self.getLast(fro,ID)
                return

            if xmlns=="jabber:iq:version" and iqType=="get":
                self.getVersion(fro,ID)
                return

            if xmlns=="jabber:iq:gateway" and iqType=="get":
                self.getIqGateway(fro,ID)
                return

            if xmlns=="jabber:iq:gateway" and iqType=="set":
                self.setIqGateway(el,fro,ID)
                return

            if xmlns=="vcard-temp" and iqType=="get" and query.name=="vCard":
                self.getvcard(fro,ID)
                return

            if xmlns=="http://jabber.org/protocol/commands" and query.name=="command" and iqType=="set":
                self.adhoc.onCommand(query,fro,ID,node)
                return

            if xmlns=="http://jabber.org/protocol/stats":
                self.getStats(el,fro,ID)
                return

            self.sendIqError(to=fro.full(), fro=config.JID, ID=ID, xmlns=xmlns, etype="cancel", condition="feature-not-implemented")

    def getStats(self,el,fro,ID):
        iq = Element((None,"iq"))
        iq.attributes["type"]="result"
        iq.attributes["from"]=config.JID
        iq.attributes["to"]=fro.full()
        if ID:
            iq.attributes["id"]=ID
        query=iq.addElement("query")
        query.attributes["xmlns"]="http://jabber.org/protocol/stats"
        nodes=xpath.XPathQuery("/iq/query[@xmlns='http://jabber.org/protocol/stats']/stat").queryForNodes(el)
        if nodes:
            for node in nodes:
                if node.getAttribute("name")=="users/online":
                    o=query.addElement("stat")
                    o.attributes["name"]="users/online"
                    o.attributes["units"]="users"
                    o.attributes["value"]=str(len(self.clients.keys()))
                if node.getAttribute("name")=="users/total":
                    t=query.addElement("stat")
                    t.attributes["name"]="users/total"
                    t.attributes["units"]="users"
                    t.attributes["value"]=str(self.db.getCount("users"))
        else:
            query.addElement("stat").attributes["name"]="users/online"
            query.addElement("stat").attributes["name"]="users/total"
        self.send(iq)

    def getvcard(self,fro,ID):
        iq = Element((None,"iq"))
        iq.attributes["type"]="result"
        iq.attributes["from"]=config.JID
        iq.attributes["to"]=fro.full()
        if ID:
            iq.attributes["id"]=ID
        vcard=iq.addElement("vCard")
        vcard.attributes["xmlns"]="vcard-temp"
        vcard.addElement("NICKNAME",content="J2J")
        vcard.addElement("DESC",content="Jabber-To-Jabber Transport (GTalk, LiveJournal inside)")
        vcard.addElement("URL",content="http://JRuDevels.org")
        self.send(iq)

    def getRegister(self,el,fro,ID):
        iq = Element((None,"iq"))
        iq.attributes["type"]="result"
        iq.attributes["from"]=config.JID
        iq.attributes["to"]=fro.full()
        if ID:
            iq.attributes["id"]=ID
        query=iq.addElement("query")
        query.attributes["xmlns"]="jabber:iq:register"
        form=utils.createForm(query,"form")
        utils.addTitle(form,"J2J Registration Form")
        uid=self.db.getIdByJid(fro.userhost())
        if uid:
            edit=True
            data=self.db.getDataById(uid)
        else:
            edit=False
            data=[None,None,None,None,5222]
        if not edit:
            utils.addLabel(form,"Please enter data for your Jabber-account")
        else:
            utils.addLabel(form,"Please edit data")
        utils.addTextBox(form,"username","Username",data[0],required=True)
        utils.addTextPrivate(form,"password","Password",data[1],required=True)
        utils.addTextBox(form,"server","Server",data[2],required=True)
        utils.addTextBox(form,"domain","Domain or IP",data[3])
        utils.addTextBox(form,"port","Port",str(data[4]))
        self.send(iq)

    def setRegister(self,el,fro,ID):
        uid=self.db.getIdByJid(fro.userhost())
        if uid:
            edit=True
        else:
            edit=False
        if xpath.XPathQuery("/iq/query[@xmlns='jabber:iq:register']/remove").matches(el):
            if not edit:
                self.sendIqError(to=fro.full(), fro=config.JID, ID=ID, xmlns='jabber:iq:register', etype="cancel", condition="registration-required")
                return
            for j in self.clients.keys():
                if j.find(fro.userhost()+"/")==0:
                    if self.clients[j].connected:
                        self.clients[j].xmlstream.sendFooter()
            unPres=Element((None,"presence"))
            unPres.attributes["to"]=fro.full()
            unPres.attributes["type"]="unavailable"
            if self.clients.has_key(fro.full()):
                for ojid in self.clients[fro.full()].presences_available_full:
                    unPres.attributes["from"]=utils.quoteJID(ojid)
                    self.send(unPres)
            ujids=self.db.fetchall("SELECT jid FROM %s WHERE id='%s'" % (self.db.dbTablePrefix+"rosters",str(uid)))
            for ojid in ujids:
                unPres.attributes["from"]=utils.quoteJID(ojid[0])
                unPres.attributes["type"]="unsubscribe"
                self.send(unPres)
                unPres.attributes["type"]="unsubscribed"
                self.send(unPres)
            self.db.execute("DELETE from "+self.db.dbTablePrefix+"rosters WHERE id="+str(uid))
            self.db.execute("DELETE from "+self.db.dbTablePrefix+"users_options WHERE id="+str(uid))
            self.db.execute("DELETE from "+self.db.dbTablePrefix+"users WHERE id="+str(uid))
            self.db.commit()
            self.sendIqResult(fro.full(),config.JID,ID,"jabber:iq:register")
            pres=Element((None,"presence"))
            pres.attributes["to"]=fro.full()
            pres.attributes["from"]=config.JID
            pres.attributes["type"]="unsubscribe"
            self.send(pres)
            pres.attributes["type"]="unsubscribed"
            self.send(pres)
            pres.attributes["type"]="unavailable"
            self.send(pres)
            return
        formXPath="/iq/query[@xmlns='jabber:iq:register']/x[@xmlns='jabber:x:data'][@type='submit']"
        username=xpath.queryForString(formXPath+"/field[@var='username']/value",el)
        if username=='':
            self.sendIqError(to=fro.full(), fro=config.JID, ID=ID, xmlns='jabber:iq:register', etype="cancel", condition="not-acceptable")
            return
        password=xpath.XPathQuery(formXPath+"/field[@var='password']/value").queryForString(el)
        if password=='':
            self.sendIqError(to=fro.full(), fro=config.JID, ID=ID, xmlns='jabber:iq:register', etype="cancel", condition="not-acceptable")
            return
        server=xpath.XPathQuery(formXPath+"/field[@var='server']/value").queryForString(el)
        if server=='':
            self.sendIqError(to=fro.full(), fro=config.JID, ID=ID, xmlns='jabber:iq:register', etype="cancel", condition="not-acceptable")
            return
        domain=xpath.XPathQuery(formXPath+"/field[@var='domain']/value").queryForString(el)
        port=xpath.XPathQuery(formXPath+"/field[@var='port']/value").queryForString(el)
        try:
            port=int(port)
        except:
            port=5222
        if not edit:
            self.db.execute("INSERT INTO "+self.db.dbTablePrefix+"users (jid,username,domain,server,password,port) VALUES ( '"+self.db.dbQuote(fro.userhost().encode('utf-8'))+"', '"+self.db.dbQuote(username.encode('utf-8'))+"', '"+self.db.dbQuote(domain.encode('utf-8'))+"', '"+self.db.dbQuote(server.encode('utf-8'))+"', '"+self.db.dbQuote(password.encode('utf-8'))+"', "+str(port)+")")
            uid=self.db.getIdByJid(fro.userhost())
            self.db.execute("INSERT INTO "+self.db.dbTablePrefix+"users_options ( id ) VALUES  ('"+str(uid)+"')")
            self.db.commit()
            self.sendIqResult(fro.full(),config.JID,ID,"jabber:iq:register")
            pres=Element((None,"presence"))
            pres.attributes["to"]=fro.userhost()
            pres.attributes["from"]=config.JID
            pres.attributes["type"]="subscribe"
            self.send(pres)
            if config.ADMINS!=[]:
                msg=Element((None,"message"))
                msg.attributes["type"]="chat"
                msg.attributes["from"]=config.JID
                msg.addElement("body",content="J2J %s Registration notify:\nHost JID:%s\nGuest JID:%s" % (config.JID,fro.full(),username+"@"+server))
            for ajid in config.ADMINS:
                msg.attributes["to"]=ajid
                self.send(msg)
        elif edit:
            data=self.db.getDataById(uid)
            if data[0]!=username or data[2]!=server:
                a=self.db.fetchall("SELECT jid FROM %s WHERE id='%s'" % (self.db.dbTablePrefix+"rosters",str(uid)))
                for unjid in a:
                    pres=Element((None,"presence"))
                    pres.attributes["to"]=fro.userhost()
                    pres.attributes["from"]=utils.quoteJID(unjid[0])
                    pres.attributes["type"]="unsubscribe"
                    self.send(pres)
                    pres.attributes["type"]="unsubscribed"
                    self.send(pres)
                self.db.execute("DELETE FROM %s WHERE id='%s'" % (self.db.dbTablePrefix+"rosters",str(uid)))
            self.db.execute("UPDATE %s SET username='%s', domain='%s', server='%s', password='%s', port=%s WHERE id='%s'" % (self.db.dbTablePrefix+"users",self.db.dbQuote(username),self.db.dbQuote(domain),self.db.dbQuote(server),self.db.dbQuote(password),str(port),str(uid)))
            self.db.commit()
            self.sendIqResult(fro.full(),config.JID,ID,"jabber:iq:register")

    def getIqGateway(self,fro,ID):
        iq = Element((None,"iq"))
        iq.attributes["type"]="result"
        iq.attributes["from"]=config.JID
        iq.attributes["to"]=fro.full()
        if ID:
            iq.attributes["id"]=ID
        query=iq.addElement("query")
        query.attributes["xmlns"]="jabber:iq:gateway"
        query.addElement("desc",content="Enter XMPP name below")
        query.addElement("prompt",content="XMPP name")
        self.send(iq)

    def setIqGateway(self,el,fro,ID):
        iq = Element((None,"iq"))
        iq.attributes["type"]="result"
        iq.attributes["from"]=config.JID
        iq.attributes["to"]=fro.full()
        if ID:
            iq.attributes["id"]=ID
        prompt=xpath.XPathQuery('/iq/query[@xmlns="jabber:iq:gateway"]/prompt').queryForString(el)
        if prompt==None:
            prompt=''
        query=iq.addElement("query")
        query.attributes["xmlns"]="jabber:iq:gateway"
        query.addElement("jid",content=utils.quoteJID(prompt))
        self.send(iq)

    def getLast(self,fro,ID):
        iq = Element((None,"iq"))
        iq.attributes["type"]="result"
        iq.attributes["from"]=config.JID
        iq.attributes["to"]=fro.full()
        if ID:
            iq.attributes["id"]=ID
        query=iq.addElement("query")
        query.attributes["xmlns"]="jabber:iq:last"
        query.attributes["seconds"]=str(int(time.time()-self.startTime))
        self.send(iq)

    def getVersion(self,fro,ID):
        iq = Element((None,"iq"))
        iq.attributes["type"]="result"
        iq.attributes["from"]=config.JID
        iq.attributes["to"]=fro.full()
        if ID:
            iq.attributes["id"]=ID
        query=iq.addElement("query")
        query.attributes["xmlns"]="jabber:iq:version"
        query.addElement("name",content="J2J Transport (http://JRuDevels.org) Twisted-version")
        query.addElement("version",content=self.VERSION)
        self.send(iq)

    def getDiscoInfo(self,el,fro,ID,node):
        iq = Element((None, "iq"))
        iq.attributes["type"] = "result"
        iq.attributes["from"] = config.JID
        iq.attributes["to"] = fro.full()
        if ID:
            iq.attributes["id"] = ID
        query = iq.addElement("query")
        query.attributes["xmlns"] = "http://jabber.org/protocol/disco#info"
        if node:
            query.attributes["node"] = node
            if node=='http://jabber.org/protocol/commands':
                identity=query.addElement("identity")
                identity.attributes["name"]="Commands"
                identity.attributes["category"]="automation"
                identity.attributes["type"]="command-list"
            if node in self.adhoc.commands.keys():
                if self.adhoc.commands[node][3]:
                    uid=self.db.getIdByJid(fro.userhost())
                    if not uid:
                        self.sendIqError(to=fro.full(), fro=config.JID, ID=ID, xmlns='http://jabber.org/protocol/disco#info', etype="cancel", condition="not-authorized")
                        return
                identity=query.addElement("identity")
                identity.attributes["name"]=self.adhoc.commands[node][0]
                identity.attributes["category"]="automation"
                identity.attributes["type"]="command-node"
                query.addElement("feature").attributes["var"]="http://jabber.org/protocol/commands"
                query.addElement("feature").attributes["var"]="jabber:x:data"
            if node.startswith("groster") and self.clients.has_key(fro.full()):
                query.addElement("feature").attributes["var"]="http://jabber.org/protocol/disco#items"
                query.addElement("feature").attributes["var"]="http://jabber.org/protocol/disco#info"
        else:
            identity=query.addElement("identity")
            identity.attributes["name"]="J2J: XMPP-Transport"
            identity.attributes["category"]="gateway"
            identity.attributes["type"]="XMPP"
            query.addElement("feature").attributes["var"]="vcard-temp"
            query.addElement("feature").attributes["var"]="http://jabber.org/protocol/commands"
            query.addElement("feature").attributes["var"]="http://jabber.org/protocol/stats"
            query.addElement("feature").attributes["var"]="http://jabber.org/protocol/disco#items"
            query.addElement("feature").attributes["var"]="http://jabber.org/protocol/disco#info"
            query.addElement("feature").attributes["var"]="jabber:iq:gateway"
            query.addElement("feature").attributes["var"]="jabber:iq:register"
            query.addElement("feature").attributes["var"]="jabber:iq:last"
            query.addElement("feature").attributes["var"]="jabber:iq:version"
        self.send(iq)

    def getDiscoItems(self,el,fro,ID,node):
        iq = Element((None,"iq"))
        iq.attributes["type"] = "result"
        iq.attributes["from"] = config.JID
        iq.attributes["to"] = fro.full()
        if ID:
            iq.attributes["id"] = ID
        query = iq.addElement("query")
        query.attributes["xmlns"] = "http://jabber.org/protocol/disco#items"
        if node:
            query.attributes["node"] = node
        if node==None:
            utils.addDiscoItem(query,config.JID,"Commands",'http://jabber.org/protocol/commands')
            self.adhoc.getCommandsList(query)
            if self.clients.has_key(fro.full()):
                utils.addDiscoItem(query,utils.quoteJID(self.clients[fro.full()].client_jid.host),"Guest's server Discovery")
                utils.addDiscoItem(query,config.JID,"Guest roster","groster")
        elif node=="groster" and self.clients.has_key(fro.full()):
            groups = self.clients[fro.full()].roster.getGroups()
            for group in groups:
                utils.addDiscoItem(query,config.JID,group,"groster/"+group)
        elif node.startswith("groster/") and self.clients.has_key(fro.full()):
            group=node[8:]
            contacts=self.clients[fro.full()].roster.getAllInGroup(group)
            for contact in contacts:
                utils.addDiscoItem(query,contact[0],contact[1])
        elif node=="http://jabber.org/protocol/commands":
            self.adhoc.getCommandsList(query)
        elif node in self.adhoc.commands.keys():
            if self.adhoc.commands[node][3]:
                uid=self.db.getIdByJid(fro.userhost())
                if not uid:
                    self.sendIqError(to=fro.full(), fro=config.JID, ID=ID, xmlns='http://jabber.org/protocol/disco#items', etype="cancel", condition="not-authorized")
                    return
        self.send(iq)

    def sendIqResult(self, to, fro, ID, xmlns):
        el = Element((None,"iq"))
        el.attributes["to"] = to
        el.attributes["from"] = fro
        if ID:
            el.attributes["id"] = ID
            el.attributes["type"] = "result"
            self.send(el)

    def sendIqError(self, to, fro, ID, xmlns, etype, condition):
        el = Element((None, "iq"))
        el.attributes["to"] = to
        el.attributes["from"] = fro
        if ID:
            el.attributes["id"] = ID
            el.attributes["type"] = "error"
            error = el.addElement("error")
            error.attributes["type"] = etype
            error.attributes["code"] = str(utils.errorCodeMap[condition])
            cond = error.addElement(condition)
            cond.attributes["xmlns"]="urn:ietf:params:xml:ns:xmpp-stanzas"
            self.send(el)

    def sendPresenceError(self, to, fro, etype, condition):
        el = Element((None, "presence"))
        el.attributes["to"] = to
        el.attributes["from"] = fro
        el.attributes["type"] = "error"
        error = el.addElement("error")
        error.attributes["type"] = etype
        error.attributes["code"] = str(utils.errorCodeMap[condition])
        cond=error.addElement(condition)
        cond.attributes["xmlns"]="urn:ietf:params:xml:ns:xmpp-stanzas"
        self.send(el)

#def kill(a,b):
    #print "!"
    #for client in self.clients.keys():
        #if self.clients[client].connected:
            #self.clients[client].xmlstream.sendFooter()
        #else:
            #self.clients[client].disconnect=True

#if os.name == "posix":
    #import signal
    #signal.signal(signal.SIGTERM, kill)

c=j2jComponent(reactor)
f=component.componentFactory(config.JID,config.PASSWORD)
connector = component.buildServiceManager(config.JID, config.PASSWORD, "tcp:%s:%s" % (config.HOST, config.PORT))
c.setServiceParent(connector)
connector.startService()
reactor.run()