from twisted.words.xish.domish import Element

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
        iqType=el.attributes["type"]
        if not iqType in ["set","result"]: return
        for query in el.elements():
            for item in query.elements():
                if item.name=="item":
                    r=self.getItem(item)
                    if r[1][1]=="remove" and self.items.has_key(r[0]):
                        del self.items[r[0]]
                    elif r[1][1]!="remove":
                        self.items[r[0]]=r[1]
        if iqType=="set":
            result=Element((None,"iq"))
            result.attributes["type"]="result"
            result.attributes["id"]=el.attributes["id"]
            result.attributes["to"]=el.attributes["to"]
            result.attributes["from"]=el.attributes["from"]
            self.host.xmlstream.send(result)
