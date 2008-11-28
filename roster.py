# Part of J2J (http://JRuDevels.org)
# Copyright 2007 JRuDevels.org

import utils

from twisted.words.xish.domish import Element

__id__ = "$Id$"

class roster:
    def __init__(self,host):
        self.host=host
        self.items={}

    def getItem(self,el):
        cjid=el.attributes['jid']
        item=[]
        if el.attributes.has_key('name'):
            item.append(el.attributes['name'])
        else:
            item.append(None)
        if el.attributes.has_key('subscription'):
            item.append(el.attributes['subscription'])
        else:
            item.append(None)
        groups=[]
        for groupEl in el.elements():
            if groupEl.name=="group":
                groups.append(unicode(groupEl))
        item.append(groups)
        return (cjid,item)

    def getGroups(self):
        groups=[]
        alreadyUndefined=False
        for contact in self.items.keys():
            if self.items[contact][2]==[] and not alreadyUndefined:
                groups.append(u"Undefined")
                alreadyUndefined=True
            else:
                for group in self.items[contact][2]:
                    if not group in groups:
                        groups.append(group)
        return groups

    def getAllInGroup(self,group):
        if group=="Undefined": group=None
        all=[]
        for contact in self.items.keys():
            if group:
                if group in self.items[contact][2]:
                    con=[contact,self.items[contact][0]]
                    all.append(con)
            elif self.items[contact][2]==[]:
                con=[contact,self.items[contact][0]]
                all.append(con)
        return all

    def onIq(self,el):
        iqFrom=el.getAttribute("from")
        if not iqFrom in (None, self.host.client_jid.full(), self.host.client_jid.userhost()):
            self.host.component.sendIqError(el.getAttribute("from"),el.getAttribute("to"),el.getAttribute("id"),"cancel","not-acceptable",sender=self.host)
            return
        iqType=el.attributes["type"]
        if not iqType in ["set","result"]: return
        if not self.host.presenceSent:
            presence=Element((None,'presence'))
            presence.attributes['to']=self.host.host_jid.full()
            presence.attributes['from']=self.host.config.JID
            presence.addElement('status',content="Online")
            self.host.component.send(presence)
            self.host.presenceSent=True
        for query in el.elements():
            for item in query.elements():
                if item.name=="item":
                    r=self.getItem(item)
                    if r[1][1]=="remove" and self.items.has_key(r[0]):
                        del self.items[r[0]]
                    elif r[1][1]!="remove":
                        self.items[r[0]]=r[1]
        db=self.host.component.db
        uid=db.getIdByJid(self.host.host_jid.userhost())
        if uid and self.host.import_roster:
            dbroster=db.fetchall("SELECT jid FROM %s WHERE id='%s'" % (db.dbTablePrefix+"rosters",str(uid)))
            presence=Element((None,'presence'))
            presence.attributes['to']=self.host.host_jid.userhost()
            for i in dbroster:
                jid,=i
                if not jid in self.items:
                    presence.attributes['from']=utils.quoteJID(jid,self.host.config.JID)
                    presence.attributes['type']='unsubscribe'
                    self.host.component.send(presence)
                    presence.attributes['type']='unsubscribed'
                    self.host.component.send(presence)
                    db.execute("DELETE FROM %s WHERE id='%s' and jid='%s'" % (db.dbTablePrefix+"rosters", str(uid), db.dbQuote(jid.encode("utf-8"))))
            for jid in self.items.keys():
                if not jid in dbroster:
                    presence=Element((None,'presence'))
                    presence.attributes['to']=self.host.host_jid.userhost()
                    presence.attributes['type']='subscribe'
                    presence.attributes['from']=utils.quoteJID(jid,self.host.config.JID)
                    if self.items[jid][0]:
                        nickEl=presence.addElement('nick','http://jabber.org/protocol/nick',content=self.items[jid][0])
                        #nickEl.attributes['xmlns']=''
                    self.host.component.send(presence)
                    db.execute("INSERT INTO %s (id,jid) VALUES ('%s','%s')" % (db.dbTablePrefix+"rosters", str(uid), db.dbQuote(jid.encode("utf-8"))))
            db.commit()
        if iqType=="set":
            result=Element((None,"iq"))
            result.attributes["type"]="result"
            if el.getAttribute("id"):
                result.attributes["id"]=el.getAttribute("id")
            if el.getAttribute("from"):
                result.attributes["to"]=el.getAttribute("from")
            if el.getAttribute("to"):
                result.attributes["from"]=el.getAttribute("to")
            self.host.xmlstream.send(result)

    def removeItem(self,jid):
        if jid in self.items.keys():
            iq=Element((None,'iq'))
            iq.attributes['type']='set'
            query=iq.addElement('query','jabber:iq:roster')
            item=query.addElement('item')
            item.attributes['jid']=jid
            item.attributes['subscription']='remove'
            self.host.xmlstream.send(iq)
